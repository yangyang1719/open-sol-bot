import base64
import os
import struct

from solbot_cache import AccountAmountCache, MintAccountCache, get_min_balance_rent
from solbot_common.constants import ( METEORA_DBC_PROGRAM,
                                     ACCOUNT_LAYOUT_LEN,
                                     POOL_AUTHORITY,
                                     METEORA_DBC_SWAP,
                                     REFERRAL_TOKEN_ACC,
                                     EVENT_AUTH,
                                     TOKEN_PROGRAM_ID, WSOL)
from solbot_common.layouts.meteora_dbc import (
    PoolState,
    PoolConfig,
    fetch_pool_state,
    fetch_pool_config,
    swap_base_to_quote, 
    swap_quote_to_base,
    fetch_pool_from_rpc
)
from solbot_common.log import logger
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.transaction import VersionedTransaction  # type: ignore
from spl.token.instructions import (
    InitializeAccountParams,
    create_associated_token_account,
    initialize_account,
    CloseAccountParams, 
    close_account,
    get_associated_token_address)
from solders.instruction import AccountMeta, Instruction  # type: ignore
from solders.system_program import CreateAccountWithSeedParams, create_account_with_seed  # type: ignore

from trading.swap import SwapDirection, SwapInType
from trading.tx import build_transaction
from trading.utils import (has_ata, max_amount_with_slippage,
                           min_amount_with_slippage)

from .base import TransactionBuilder


class MeteoraDBCTransactionBuilder(TransactionBuilder):
    async def build_swap_transaction(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
        priority_fee: float | None = None,
    ) -> VersionedTransaction:
        if swap_direction == "sell" and in_type is None:
            raise ValueError("in_type must be specified when selling")

        owner = keypair.pubkey()
        mint = Pubkey.from_string(token_address)
        program_id = TOKEN_PROGRAM_ID
        native_mint = WSOL

        if swap_direction == SwapDirection.Buy:
            token_in = native_mint
            token_out = mint
        elif swap_direction == SwapDirection.Sell:
            token_in = mint
            token_out = native_mint
        else:
            raise ValueError("swap_direction must be buy or sell")

        logger.info(f"Starting buy transaction for pool: {token_address}")

        pool_str = await fetch_pool_from_rpc(self.rpc_client, token_address)
        logger.info("Fetching pool state...")
        pool_state: PoolState = await fetch_pool_state(self.rpc_client, pool_str)
        logger.info("Fetching pool config...")
        pool_config: PoolConfig = await fetch_pool_config(self.rpc_client, pool_state.config)
        quote_token_decimals = pool_config.token_decimal
        quote_amount_in = int(ui_amount * 10 ** quote_token_decimals)
        if pool_config.quote_mint != WSOL:
            raise ValueError("swap for this pool is not supported, the quote token must be WSOL")
        if pool_config.base_mint != token_address:
            raise ValueError("swap for this pool is not supported, the base token must be the same as the pool")

        curve: list[tuple[int, int]] = [
            (pt.sqrt_price, pt.liquidity)
            for pt in pool_config.curve
            if pt.sqrt_price != 0
        ]
        cliff_fee_num    = pool_config.pool_fees.base_fee.cliff_fee_numerator
        protocol_fee_pct = pool_config.pool_fees.protocol_fee_percent
        referral_fee_pct = pool_config.pool_fees.referral_fee_percent

        seed = base64.urlsafe_b64encode(os.urandom(24)).decode("utf-8")
        quote_token_account = Pubkey.create_with_seed(
            owner,
            seed,
            TOKEN_PROGRAM_ID,
        )
        quote_rent = await get_min_balance_rent()

        create_quote_token_account_ix = create_account_with_seed(
            CreateAccountWithSeedParams(
                from_pubkey=owner,
                to_pubkey=quote_token_account,
                base=owner,
                seed=seed,
                lamports=int(quote_rent + quote_amount_in),
                space=ACCOUNT_LAYOUT_LEN,
                owner=TOKEN_PROGRAM_ID,
            )
        )
        init_quote_token_account_ix = initialize_account(
            InitializeAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=quote_token_account,
                mint=pool_config.quote_mint,
                owner=owner,
            )
        )

        in_ata = get_associated_token_address(owner=owner, mint=token_in)
        out_ata = get_associated_token_address(owner=owner, mint=token_out)

        create_instruction = None
        close_instruction = None
        if swap_direction == SwapDirection.Buy:
            estimate = swap_quote_to_base(
                amount_in=quote_amount_in,
                cliff_fee_num=cliff_fee_num,
                protocol_fee_pct=protocol_fee_pct,
                referral_fee_pct=referral_fee_pct,
                cur_sqrt=pool_state.sqrt_price,
                curve=curve
            )
            logger.info(f"Quote→Base estimate: {estimate}")
            # 如果 ata 账户不存在，需要创建
            if not await has_ata(
                self.rpc_client,
                owner,
                token_out,
            ):
                create_instruction = create_associated_token_account(owner, owner, token_out)
           
            amount_specified = int(estimate["outputAmount"])
            min_sol_cost = min_amount_with_slippage(amount_specified, slippage_bps)
           
            input_accounts = [
                AccountMeta(POOL_AUTHORITY, False, False),
                AccountMeta(pool_state.config, False, False),
                AccountMeta(pool_state.pool, False, True),
                AccountMeta(quote_token_account, False, True),
                AccountMeta(out_ata, False, True),
                AccountMeta(pool_state.base_vault, False, True),
                AccountMeta(pool_state.quote_vault, False, True),
                AccountMeta(pool_state.base_mint, False, False),
                AccountMeta(pool_config.quote_mint, False, False),
                AccountMeta(owner, True, True),
                AccountMeta(TOKEN_PROGRAM_ID, False, False),
                AccountMeta(TOKEN_PROGRAM_ID, False, False),
                AccountMeta(REFERRAL_TOKEN_ACC, False, False),
                AccountMeta(EVENT_AUTH, False, False),
                AccountMeta(METEORA_DBC_PROGRAM, False, False),
            ]
        elif swap_direction == SwapDirection.Sell:
            in_amount = await AccountAmountCache().get_amount(in_ata)
            in_mint = await MintAccountCache().get_mint_account(token_in)
            if in_mint is None:
                raise Exception("in_mint not found")
           
           

            if in_type == SwapInType.Pct:
                amount_in_pct = min(ui_amount, 1)
                if amount_in_pct < 0:
                    raise Exception("amount_in_pct must be greater than 0, range [0, 1]")

                if amount_in_pct == 1:
                    # sell all, close ata
                    logger.info(f"Sell all, will be close ATA for mint {token_in}")
                    close_instruction = close_account(
                        CloseAccountParams(
                            program_id=program_id,
                            account=in_ata,
                            dest=owner,
                            owner=owner,
                        )
                    )
                    amount_specified = in_amount
                else:
                    amount_specified = int(in_amount * amount_in_pct)
            elif in_type == SwapInType.Qty:
                amount_specified = int(ui_amount * 10**in_mint.decimals)
            else:
                raise Exception("in_type must be qty or pct")
            estimate = swap_base_to_quote(
                amount_in=amount_specified,
                cliff_fee_num=cliff_fee_num,
                protocol_fee_pct=protocol_fee_pct,
                referral_fee_pct=referral_fee_pct,
                cur_sqrt=pool_state.sqrt_price,
                curve=curve
            )
            logger.info(f"Base→Quote estimate: {estimate}")
            sol_output = int(estimate["outputAmount"])
            min_sol_cost = min_amount_with_slippage(sol_output, slippage_bps)
            quote_amount_in=amount_specified
            input_accounts = [
                AccountMeta(POOL_AUTHORITY, False, False),
                AccountMeta(pool_state.config, False, False),
                AccountMeta(pool_state.pool, False, True),
                AccountMeta(in_ata, False, True),
                AccountMeta(quote_token_account, False, True),
                AccountMeta(pool_state.base_vault, False, True),
                AccountMeta(pool_state.quote_vault, False, True),
                AccountMeta(pool_state.base_mint, False, False),
                AccountMeta(pool_config.quote_mint, False, False),
                AccountMeta(owner, True, True),
                AccountMeta(TOKEN_PROGRAM_ID, False, False),
                AccountMeta(TOKEN_PROGRAM_ID, False, False),
                AccountMeta(REFERRAL_TOKEN_ACC, False, False),
                AccountMeta(EVENT_AUTH, False, False),
                AccountMeta(METEORA_DBC_PROGRAM, False, False),
            ]


        instructions = [
            create_quote_token_account_ix,
            init_quote_token_account_ix,
        ]
        data = bytearray.fromhex(METEORA_DBC_SWAP)
        data.extend(struct.pack("<Q", quote_amount_in))
        data.extend(struct.pack("<Q", min_sol_cost))
        build_swap_instruction = Instruction(METEORA_DBC_PROGRAM, bytes(data), input_accounts)
        logger.debug(f"Build swap input accounts: {input_accounts}")
        close_quote_token_account_ix = close_account(
            CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=quote_token_account,
                dest=owner,
                owner=owner,
            )
        )
        if create_instruction is not None:
            instructions.append(create_instruction)
            logger.debug(f"Create instruction: {create_instruction}")
        if amount_specified > 0:
            instructions.append(build_swap_instruction)
            logger.debug(f"Swap instruction: {build_swap_instruction}")
        if close_instruction is not None:
            instructions.append(close_instruction)
            logger.debug(f"Close instruction: {close_instruction}")
        instructions.append(close_quote_token_account_ix)

        if len(instructions) == 0:
            raise Exception("instructions is empty")

        logger.debug(f"Swap instructions: {instructions}")

        return await build_transaction(
            keypair=keypair,
            instructions=instructions,
            priority_fee=priority_fee,
            use_jito=use_jito,
        )

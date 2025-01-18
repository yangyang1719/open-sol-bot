import base64
import os

from loguru import logger
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed
from solana.rpc.types import TokenAccountOpts, TxOpts
from solders.instruction import Instruction  # type: ignore[reportMissingModuleSource]
from solders.keypair import Keypair  # type: ignore[reportMissingModuleSource]
from solders.pubkey import Pubkey  # type: ignore[reportMissingModuleSource]
from solders.rpc.responses import RpcSimulateTransactionResult  # type: ignore
from solders.signature import Signature  # type: ignore[reportMissingModuleSource]
from solders.system_program import (  # type: ignore[reportMissingModuleSource]
    CreateAccountWithSeedParams,
    create_account_with_seed,
)
from solders.transaction import VersionedTransaction  # type: ignore
from spl.token.instructions import (
    CloseAccountParams,
    InitializeAccountParams,
    close_account,
    create_associated_token_account,
    get_associated_token_address,
    initialize_account,
)

from cache import MinBalanceRentCache
from cache.auto.raydium_pool import get_preferred_pool
from common.config import settings
from common.constants import ACCOUNT_LAYOUT_LEN, SOL_DECIMAL, TOKEN_PROGRAM_ID, WSOL
from common.utils.pool import (
    AmmV4PoolKeys,
    get_amm_v4_reserves,
    make_amm_v4_swap_instruction,
)
from common.utils.utils import get_token_balance
from trading.swap import SwapDirection, SwapInType
from trading.tx import build_transaction

from .proto import TraderProtocol


def sol_for_tokens(sol_amount, base_vault_balance, quote_vault_balance, swap_fee=0.25):
    effective_sol_used = sol_amount - (sol_amount * (swap_fee / 100))
    constant_product = base_vault_balance * quote_vault_balance
    updated_base_vault_balance = constant_product / (
        quote_vault_balance + effective_sol_used
    )
    tokens_received = base_vault_balance - updated_base_vault_balance
    return round(tokens_received, 9)


def tokens_for_sol(
    token_amount, base_vault_balance, quote_vault_balance, swap_fee=0.25
):
    effective_tokens_sold = token_amount * (1 - (swap_fee / 100))
    constant_product = base_vault_balance * quote_vault_balance
    updated_quote_vault_balance = constant_product / (
        base_vault_balance + effective_tokens_sold
    )
    sol_received = quote_vault_balance - updated_quote_vault_balance
    return round(sol_received, 9)


class RayV4(TraderProtocol):
    def __init__(self, rpc_client: AsyncClient) -> None:
        self.rpc_client = rpc_client

    async def build_buy_instructions(
        self,
        payer_keypair: Keypair,
        token_address: str,
        sol_in: float,
        slippage_bps: int,
    ) -> list[Instruction]:
        pool_data = await get_preferred_pool(token_address)
        if pool_data is None:
            raise ValueError("Error fetching pool data")

        pool_id = pool_data["pool_id"]
        pool_keys = AmmV4PoolKeys.from_pool_data(
            pool_id, pool_data["amm_data"], pool_data["market_data"]
        )
        if pool_keys is None:
            raise ValueError("Error fetching pool keys")

        mint = (
            pool_keys.base_mint if pool_keys.base_mint != WSOL else pool_keys.quote_mint
        )
        amount_in = int(sol_in * SOL_DECIMAL)

        base_reserve, quote_reserve, token_decimal = await get_amm_v4_reserves(
            pool_keys
        )
        amount_out = sol_for_tokens(sol_in, base_reserve, quote_reserve)

        logger.info(
            "Estimated amount out for buying {} SOL: {} tokens".format(
                sol_in, amount_out
            )
        )

        slippage_adjustment = 1 - (slippage_bps / 10000)
        amount_out_with_slippage = amount_out * slippage_adjustment
        minimum_amount_out = int(amount_out_with_slippage * 10**token_decimal)
        logger.info(
            f"Amount In: {amount_in} | Minimum Amount Out: {minimum_amount_out}"
        )

        # 检查 token 账户是否存在
        # TODO: 引入缓存, 减少 rpc 请求
        token_account_check = await self.rpc_client.get_token_accounts_by_owner(
            payer_keypair.pubkey(), TokenAccountOpts(mint), Processed
        )
        if token_account_check.value:
            token_account = token_account_check.value[0].pubkey  # type: ignore
            create_token_account_instruction = None
        else:
            token_account = get_associated_token_address(payer_keypair.pubkey(), mint)
            create_token_account_instruction = create_associated_token_account(
                payer_keypair.pubkey(), payer_keypair.pubkey(), mint
            )
            logger.info(
                "No existing token account found; creating associated token account."
            )

        logger.debug("Generating seed for WSOL account...")
        seed = base64.urlsafe_b64encode(os.urandom(24)).decode("utf-8")
        wsol_token_account = Pubkey.create_with_seed(
            payer_keypair.pubkey(), seed, TOKEN_PROGRAM_ID
        )
        balance_needed = await MinBalanceRentCache.get()

        logger.debug("Creating and initializing WSOL account...")
        create_wsol_account_instruction = create_account_with_seed(
            CreateAccountWithSeedParams(
                from_pubkey=payer_keypair.pubkey(),
                to_pubkey=wsol_token_account,
                base=payer_keypair.pubkey(),
                seed=seed,
                lamports=int(balance_needed + amount_in),
                space=ACCOUNT_LAYOUT_LEN,
                owner=TOKEN_PROGRAM_ID,
            )
        )

        init_wsol_account_instruction = initialize_account(
            InitializeAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                mint=WSOL,
                owner=payer_keypair.pubkey(),
            )
        )

        logger.debug("Creating swap instructions...")
        swap_instruction = make_amm_v4_swap_instruction(
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
            token_account_in=wsol_token_account,
            token_account_out=token_account,
            accounts=pool_keys,
            owner=payer_keypair.pubkey(),
        )

        logger.debug("Preparing to close WSOL account after swap...")
        close_wsol_account_instruction = close_account(
            CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                dest=payer_keypair.pubkey(),
                owner=payer_keypair.pubkey(),
            )
        )

        # NOTE: unit_limit and unit_price 不放在这里设置，而是在 build_transaction 函数中设置
        instructions = [
            # set_compute_unit_limit(settings.trading.unit_limit),
            # set_compute_unit_price(settings.trading.unit_price),
            create_wsol_account_instruction,
            init_wsol_account_instruction,
        ]

        if create_token_account_instruction:
            instructions.append(create_token_account_instruction)

        instructions.append(swap_instruction)
        instructions.append(close_wsol_account_instruction)
        return instructions

    async def build_sell_instructions(
        self,
        payer_keypair: Keypair,
        token_address: str,
        ui_amount: float,
        in_type: SwapInType,
        slippage_bps: int,
    ) -> list[Instruction]:
        if in_type != SwapInType.Pct:
            raise NotImplementedError("Qty in_type is not implemented yet")

        percentage = ui_amount
        if 0 <= percentage <= 1:
            raise ValueError("Percentage must be between 0 and 1")

        pool_data = await get_preferred_pool(token_address)
        if pool_data is None:
            raise ValueError("Error fetching pool data")

        pool_id = pool_data["pool_id"]
        pool_keys = AmmV4PoolKeys.from_pool_data(
            pool_id, pool_data["amm_data"], pool_data["market_data"]
        )
        if pool_keys is None:
            raise ValueError("Error fetching pool keys")

        mint = (
            pool_keys.base_mint if pool_keys.base_mint != WSOL else pool_keys.quote_mint
        )
        associated_token_account = get_associated_token_address(
            payer_keypair.pubkey(), mint
        )
        token_balance = await get_token_balance(
            associated_token_account, self.rpc_client
        )
        logger.debug(f"User: {payer_keypair.pubkey()} | Token Balance: {token_balance}")
        if token_balance is None or token_balance == 0:
            raise ValueError("No token balance available to sell.")

        token_balance = token_balance * percentage
        logger.debug(
            f"Selling {percentage * 100}% of the token balance, adjusted balance: {token_balance}"
        )

        logger.debug("Calculating transaction amount...")
        base_reserve, quote_reserve, token_decimal = await get_amm_v4_reserves(
            pool_keys
        )
        amount_out = tokens_for_sol(token_balance, base_reserve, quote_reserve)
        logger.debug(f"Estimated Amount Out: {amount_out}")

        slippage_adjustment = 1 - (slippage_bps / 10000)
        amount_out_with_slippage = amount_out * slippage_adjustment
        minimum_amount_out = int(amount_out_with_slippage * SOL_DECIMAL)
        amount_in = int(token_balance * 10**token_decimal)

        logger.debug(
            f"Amount In: {amount_in} | Minimum Amount Out: {minimum_amount_out}"
        )

        logger.debug("Generating seed for WSOL account...")
        seed = base64.urlsafe_b64encode(os.urandom(24)).decode("utf-8")
        wsol_token_account = Pubkey.create_with_seed(
            payer_keypair.pubkey(), seed, TOKEN_PROGRAM_ID
        )
        balance_needed = await MinBalanceRentCache.get()

        create_wsol_account_instruction = create_account_with_seed(
            CreateAccountWithSeedParams(
                from_pubkey=payer_keypair.pubkey(),
                to_pubkey=wsol_token_account,
                base=payer_keypair.pubkey(),
                seed=seed,
                lamports=int(balance_needed),
                space=ACCOUNT_LAYOUT_LEN,
                owner=TOKEN_PROGRAM_ID,
            )
        )

        init_wsol_account_instruction = initialize_account(
            InitializeAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                mint=WSOL,
                owner=payer_keypair.pubkey(),
            )
        )

        logger.debug("Creating swap instructions...")
        swap_instructions = make_amm_v4_swap_instruction(
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
            token_account_in=associated_token_account,
            token_account_out=wsol_token_account,
            accounts=pool_keys,
            owner=payer_keypair.pubkey(),
        )

        logger.debug("Preparing to close WSOL account after swap...")
        close_wsol_account_instruction = close_account(
            CloseAccountParams(
                program_id=TOKEN_PROGRAM_ID,
                account=wsol_token_account,
                dest=payer_keypair.pubkey(),
                owner=payer_keypair.pubkey(),
            )
        )

        # NOTE: unit_limit and unit_price 不放在这里设置，而是在 build_transaction 函数中设置
        instructions = [
            # set_compute_unit_limit(settings.trading.unit_limit),
            # set_compute_unit_price(settings.trading.unit_price),
            create_wsol_account_instruction,
            init_wsol_account_instruction,
            swap_instructions,
            close_wsol_account_instruction,
        ]

        if percentage == 1:
            logger.debug("Preparing to close token account after swap...")
            close_token_account_instruction = close_account(
                CloseAccountParams(
                    program_id=TOKEN_PROGRAM_ID,
                    account=associated_token_account,
                    dest=payer_keypair.pubkey(),
                    owner=payer_keypair.pubkey(),
                )
            )
            instructions.append(close_token_account_instruction)

        return instructions

    async def build_swap_transaction(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
    ) -> VersionedTransaction:
        if swap_direction not in [SwapDirection.Buy, SwapDirection.Sell]:
            raise ValueError("swap_direction must be buy or sell")

        if swap_direction == SwapDirection.Buy:
            instructions = await self.build_buy_instructions(
                payer_keypair=keypair,
                token_address=token_address,
                sol_in=ui_amount,
                slippage_bps=slippage_bps,
            )
        elif swap_direction == SwapDirection.Sell:
            if in_type == SwapInType.Pct:
                instructions = await self.build_sell_instructions(
                    payer_keypair=keypair,
                    token_address=token_address,
                    ui_amount=ui_amount,
                    slippage_bps=slippage_bps,
                    in_type=in_type,
                )
            elif in_type == SwapInType.Qty:
                raise NotImplementedError("Qty in_type is not implemented yet")
            else:
                raise ValueError("in_type must be pct or qty")

        return await build_transaction(
            keypair=keypair,
            instructions=instructions,
            use_jito=use_jito,
        )

    async def send_transaction(self, transaction: VersionedTransaction) -> Signature:
        """Send a signed transaction.

        Args:
            transaction (VersionedTransaction): The signed transaction to send

        Returns:
            Signature: The transaction signature
        """
        resp = await self.rpc_client.send_transaction(
            transaction,
            opts=TxOpts(skip_preflight=True),
        )
        return resp.value

    async def simulate_transaction(
        self, transaction: VersionedTransaction
    ) -> RpcSimulateTransactionResult:
        """Simulate a signed transaction.

        Args:
            transaction (VersionedTransaction): The signed transaction to simulate

        Returns:
            SimulationResult: The simulation result
        """
        resp = await self.rpc_client.simulate_transaction(transaction)
        return resp.value

    async def swap(
        self,
        keypair: Keypair,
        token_address: str,
        ui_amount: float,
        swap_direction: SwapDirection,
        slippage_bps: int,
        in_type: SwapInType | None = None,
        use_jito: bool = False,
    ) -> Signature | None:
        """Swap token with GMGN API.

        Args:
            token_address (str): token address
            amount_in (float): amount in
            swap_direction (Literal["buy", "sell"]): swap direction
            slippage (int): slippage, percentage
            in_type (SwapInType | None, optional): in type. Defaults to None.
            use_jto (bool, optional): use jto. Defaults to False.
        """
        transaction = await self.build_swap_transaction(
            keypair=keypair,
            token_address=token_address,
            ui_amount=ui_amount,
            swap_direction=swap_direction,
            slippage_bps=slippage_bps,
            in_type=in_type,
            use_jito=use_jito,
        )
        if settings.trading.tx_simulate:
            await self.simulate_transaction(transaction)
            return
        else:
            return await self.send_transaction(transaction)

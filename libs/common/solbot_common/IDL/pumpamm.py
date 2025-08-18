import pathlib

from anchorpy.program.core import Program
from anchorpy.provider import Provider, Wallet
from anchorpy_core.idl import Idl  # type: ignore
from solana.rpc.async_api import AsyncClient
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from solbot_common.constants import (
    ASSOCIATED_TOKEN_PROGRAM,
    EVENT_AUTHORITY,
    PUMP_AMM_PROGRAM,
    PUMP_AMM_PROTOCOL_FEE_RECIPIENT,
    SYSTEM_PROGRAM_ID,
    TOKEN_PROGRAM_ID,
)


class PumpAmmInterface:
    def __init__(self, keypair: Keypair, client: AsyncClient):
        self.keypair = keypair
        self.client = client
        provider = Provider(connection=client, wallet=Wallet(keypair))
        idl_path = pathlib.Path(__file__).parent / "pumpamm.json"
        with open(idl_path) as f:
            idl = Idl.from_json(f.read())

        self.program = Program(idl, PUMP_AMM_PROGRAM, provider)
        self.connection = provider.connection

    @staticmethod
    def get_coin_creator_vault_authority_pda(coin_creator: Pubkey) -> Pubkey:
        """计算代币创建者金库权限 PDA"""
        seeds = [b"creator_vault", bytes(coin_creator)]
        pda, _ = Pubkey.find_program_address(seeds, PUMP_AMM_PROGRAM)
        return pda

    @staticmethod
    def get_global_volume_accumulator_pda() -> Pubkey:
        """计算全局交易量累加器 PDA"""
        from solbot_common.utils.utils import get_global_volume_accumulator_pda
        return get_global_volume_accumulator_pda(PUMP_AMM_PROGRAM)

    @staticmethod
    def get_user_volume_accumulator_pda(user: Pubkey, user_acc_target: Pubkey) -> Pubkey:
        """计算用户交易量累加器 PDA"""
        seeds = [b"user_volume_accumulator", bytes(user_acc_target)]
        pda, _ = Pubkey.find_program_address(seeds, PUMP_AMM_PROGRAM)
        return pda

    @staticmethod
    def get_pump_amm_global_config_pda() -> Pubkey:
        """计算 Pump AMM 全局配置 PDA"""
        seeds = [b"global_config"]  # 对应 IDL 中的种子
        pda, _ = Pubkey.find_program_address(seeds, PUMP_AMM_PROGRAM)
        return pda

    def buy(
        self,
        pool: Pubkey,
        user: Pubkey,
        global_config: Pubkey,
        base_mint: Pubkey,
        quote_mint: Pubkey,
        user_base_token_account: Pubkey,
        user_quote_token_account: Pubkey,
        pool_base_token_account: Pubkey,
        pool_quote_token_account: Pubkey,
        protocol_fee_recipient: Pubkey,
        protocol_fee_recipient_token_account: Pubkey,
        base_token_program: Pubkey,
        quote_token_program: Pubkey,
        coin_creator_vault_ata: Pubkey,
        coin_creator_vault_authority: Pubkey,
        global_volume_accumulator: Pubkey,
        user_volume_accumulator: Pubkey,
        user_acc_target: Pubkey,
        base_amount_out: int,
        quote_amount_in_max: int,
    ) -> Instruction:
        """
        执行 pump AMM 的 buy 交易
        
        Args:
            pool: AMM 池子地址
            user: 用户地址
            global_config: 全局配置地址
            base_mint: 基础代币 mint 地址
            quote_mint: 报价代币 mint 地址  
            user_base_token_account: 用户基础代币账户
            user_quote_token_account: 用户报价代币账户
            pool_base_token_account: 池子基础代币账户
            pool_quote_token_account: 池子报价代币账户
            protocol_fee_recipient: 协议费接收者
            protocol_fee_recipient_token_account: 协议费接收者代币账户
            base_token_program: 基础代币程序
            quote_token_program: 报价代币程序
            coin_creator_vault_ata: 代币创建者金库 ATA
            coin_creator_vault_authority: 代币创建者金库权限
            global_volume_accumulator: 全局交易量累加器
            user_volume_accumulator: 用户交易量累加器
            user_acc_target: 用户账户目标
            base_amount_out: 期望获得的基础代币数量
            quote_amount_in_max: 最大愿意支付的报价代币数量
        """
        buy_builder = self.program.methods["buy"]

        return (
            buy_builder.args([base_amount_out, quote_amount_in_max])
            .accounts(
                {
                    "pool": pool,
                    "user": user,
                    "global_config": global_config,
                    "base_mint": base_mint,
                    "quote_mint": quote_mint,
                    "user_base_token_account": user_base_token_account,
                    "user_quote_token_account": user_quote_token_account,
                    "pool_base_token_account": pool_base_token_account,
                    "pool_quote_token_account": pool_quote_token_account,
                    "protocol_fee_recipient": protocol_fee_recipient,
                    "protocol_fee_recipient_token_account": protocol_fee_recipient_token_account,
                    "base_token_program": base_token_program,
                    "quote_token_program": quote_token_program,
                    "system_program": SYSTEM_PROGRAM_ID,
                    "associated_token_program": ASSOCIATED_TOKEN_PROGRAM,
                    "event_authority": EVENT_AUTHORITY,
                    "program": PUMP_AMM_PROGRAM,
                    "coin_creator_vault_ata": coin_creator_vault_ata,
                    "coin_creator_vault_authority": coin_creator_vault_authority,
                    "global_volume_accumulator": global_volume_accumulator,
                    "user_volume_accumulator": user_volume_accumulator,
                    "user_acc_target": user_acc_target,
                }
            )
            .instruction()
        )

    async def buy_simple(
        self,
        pool: Pubkey,
        base_mint: Pubkey,
        quote_mint: Pubkey,
        user_base_token_account: Pubkey,
        user_quote_token_account: Pubkey,
        base_amount_out: int,
        quote_amount_in_max: int,
        coin_creator: Pubkey,
    ) -> Instruction:
        """
        简化版 buy 方法，自动计算大部分 PDA 地址
        
        Args:
            pool: AMM 池子地址
            base_mint: 基础代币 mint 地址
            quote_mint: 报价代币 mint 地址 (通常是 SOL)
            user_base_token_account: 用户基础代币账户
            user_quote_token_account: 用户报价代币账户
            base_amount_out: 期望获得的基础代币数量
            quote_amount_in_max: 最大愿意支付的报价代币数量
            coin_creator: 代币创建者地址
        - 直接从 Pool 账户读取 `pool_base_token_account` 与 `pool_quote_token_account`
        """
        from spl.token.instructions import get_associated_token_address

        user = self.keypair.pubkey()

        # 计算各种 PDA 地址
        coin_creator_vault_authority = self.get_coin_creator_vault_authority_pda(coin_creator)
        coin_creator_vault_ata = get_associated_token_address(coin_creator_vault_authority, quote_mint)
        protocol_fee_recipient_token_account = get_associated_token_address(
            PUMP_AMM_PROTOCOL_FEE_RECIPIENT,
            quote_mint,
        )
        global_volume_accumulator = self.get_global_volume_accumulator_pda()
        user_volume_accumulator = self.get_user_volume_accumulator_pda(user, user)
      # 假设池子的代币账户 - 实际使用时需要从池子账户数据中获取
        pool_base_token_account = get_associated_token_address(pool, base_mint)
        pool_quote_token_account = get_associated_token_address(pool, quote_mint)
        print(pool_base_token_account, pool_quote_token_account)
        # 从链上 Pool 账户读取两侧金库地址
        pool_account = await self.program.account["Pool"].fetch(pool)
        pool_base_token_account = pool_account.pool_base_token_account
        pool_quote_token_account = pool_account.pool_quote_token_account
        print(pool_base_token_account, pool_quote_token_account)
        return self.buy(
            pool=pool,
            user=user,
            global_config=self.get_pump_amm_global_config_pda(),
            base_mint=base_mint,
            quote_mint=quote_mint,
            user_base_token_account=user_base_token_account,
            user_quote_token_account=user_quote_token_account,
            pool_base_token_account=pool_base_token_account,
            pool_quote_token_account=pool_quote_token_account,
            protocol_fee_recipient=PUMP_AMM_PROTOCOL_FEE_RECIPIENT,
            protocol_fee_recipient_token_account=protocol_fee_recipient_token_account,
            base_token_program=TOKEN_PROGRAM_ID,
            quote_token_program=TOKEN_PROGRAM_ID,
            coin_creator_vault_ata=coin_creator_vault_ata,
            coin_creator_vault_authority=coin_creator_vault_authority,
            global_volume_accumulator=global_volume_accumulator,
            user_volume_accumulator=user_volume_accumulator,
            user_acc_target=user,
            base_amount_out=base_amount_out,
            quote_amount_in_max=quote_amount_in_max,
        )


if __name__ == "__main__":
    from solders.keypair import Keypair  # type: ignore

    from solbot_common.utils import get_async_client

    keypair = Keypair()
    wallet = Wallet(keypair)
    client = get_async_client()
    pump_fun = PumpAmmInterface(keypair, client)

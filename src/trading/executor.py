from solana.rpc.async_api import AsyncClient
from solders.keypair import Keypair  # type: ignore
from sqlmodel import select

from common.constants import PUMP_FUN_PROGRAM, RAY_V4
from common.log import logger
from common.models.tg_bot.user import User
from common.types.swap import SwapEvent
from db.session import NEW_ASYNC_SESSION, provide_session
from trading.swap import SwapDirection, SwapInType

from .swap_protocols import Gmgn, Pump, RayV4

PUMP_FUN_PROGRAM_ID = str(PUMP_FUN_PROGRAM)
RAY_V4_PROGRAM_ID = str(RAY_V4)


class TradingExecutor:
    def __init__(self, client: AsyncClient):
        self._client = client

    @provide_session
    async def __get_keypair(self, pubkey: str, *, session=NEW_ASYNC_SESSION) -> Keypair:
        stmt = select(User.private_key).where(User.pubkey == pubkey).limit(1)
        private_key = (await session.execute(stmt)).scalar_one_or_none()
        if not private_key:
            raise ValueError("Wallet not found")
        return Keypair.from_bytes(private_key)

    async def exec(self, swap_event: SwapEvent):
        if swap_event.slippage_bps is not None:
            slippage_bps = swap_event.slippage_bps
        else:
            raise ValueError("slippage_bps must be specified")

        if swap_event.swap_mode == "ExactIn":
            swap_direction = SwapDirection.Buy
        elif swap_event.swap_mode == "ExactOut":
            swap_direction = SwapDirection.Sell
        else:
            raise ValueError("swap_mode must be ExactIn or ExactOut")

        sig = None
        keypair = await self.__get_keypair(swap_event.user_pubkey)
        swap_in_type = SwapInType(swap_event.swap_in_type)

        # 如果 program_id 为 pump，则本地构建交易
        if swap_event.program_id == PUMP_FUN_PROGRAM_ID:
            logger.info("Program ID is PumpFun, So We use pump to trade")
            sig = await Pump(self._client).swap(
                keypair=keypair,
                token_address=swap_event.output_mint,
                ui_amount=swap_event.ui_amount,
                swap_direction=swap_direction,
                slippage_bps=slippage_bps,
                in_type=swap_in_type,
            )
        # NOTE: 测试下来不是很理想，暂时不启用
        # elif swap_event.program_id == RAY_V4_PROGRAM_ID:
        #     logger.info("Program ID is RayV4, So We use ray to trade")
        #     sig = await RayV4(self._client).swap(
        #         keypair=keypair,
        #         token_address=swap_event.output_mint,
        #         ui_amount=swap_event.ui_amount,
        #         swap_direction=swap_direction,
        #         slippage_bps=slippage_bps,
        #         in_type=swap_in_type,
        #     )
        elif swap_event.program_id is None:
            logger.warning("Program ID is Unknown, So We use thrid party to trade")
            sig = await Gmgn(self._client).swap(
                keypair=keypair,
                token_address=swap_event.output_mint,
                ui_amount=swap_event.ui_amount,
                swap_direction=swap_direction,
                slippage_bps=slippage_bps,
                in_type=swap_in_type,
            )
        else:
            raise ValueError(f"Program ID is not supported, {swap_event.program_id}")

        return sig

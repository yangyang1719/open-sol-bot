from solana.rpc.async_api import AsyncClient
from solbot_cache.launch import LaunchCache
from solbot_cache.rayidum import get_preferred_pool
from solbot_common.config import settings
from solbot_common.constants import PUMP_FUN_PROGRAM, RAY_V4, METEORA_DBC_PROGRAM
from solbot_common.log import logger
from solbot_common.models.tg_bot.user import User
from solbot_common.types.swap import SwapEvent
from solbot_db.session import NEW_ASYNC_SESSION, provide_session
from solders.keypair import Keypair  # type: ignore
from solders.signature import Signature  # type: ignore
from sqlmodel import select
from trading.swap import SwapDirection, SwapInType
from trading.transaction import TradingRoute, TradingService

PUMP_FUN_PROGRAM_ID = str(PUMP_FUN_PROGRAM)
RAY_V4_PROGRAM_ID = str(RAY_V4)
METEORA_DBC_PROGRAM_ID = str(METEORA_DBC_PROGRAM)


class TradingExecutor:
    def __init__(self, client: AsyncClient):
        self._rpc_client = client
        self._launch_cache = LaunchCache()
        self._trading_service = TradingService(self._rpc_client)

    @provide_session
    async def __get_keypair(self, pubkey: str, *, session=NEW_ASYNC_SESSION) -> Keypair:
        stmt = select(User.private_key).where(User.pubkey == pubkey).limit(1)
        private_key = (await session.execute(stmt)).scalar_one_or_none()
        if not private_key:
            raise ValueError("Wallet not found")
        return Keypair.from_bytes(private_key)
    
    def _get_direction_address(self, swap_event: SwapEvent) -> tuple[SwapDirection, str]:
        """ Extract the direction and address from the swap event """
        if swap_event.swap_mode == "ExactIn":
            return SwapDirection.Buy, swap_event.output_mint
        elif swap_event.swap_mode == "ExactOut":
            return SwapDirection.Sell, swap_event.input_mint
        else:
            raise ValueError("swap_mode must be ExactIn or ExactOut")

    async def find_route(self, swap_event: SwapEvent) -> TradingRoute:
        """ Find the best route for executing the swap event """
        # Check if you need to use it Pump Transactions with contract
        should_use_pump = False
        program_id = swap_event.program_id
        
        _, token_address = self._get_direction_address(swap_event)

        try:
            is_pump_token_launched = await self._launch_cache.is_pump_token_launched(token_address)
            logger.info(f"Pump token {token_address} is launched: {is_pump_token_launched}")
            if program_id == PUMP_FUN_PROGRAM_ID or (
                token_address.endswith("pump") and not is_pump_token_launched
            ):
                should_use_pump = True
                logger.info(
                    f"Token {token_address} has not launched, using Pump protocol to trade"
                )
            else:
                # Check if the token is launched on Raydium
                pool_data = await get_preferred_pool(token_address)
                if pool_data is not None:
                    logger.info(
                        f"Token {token_address} is launched on Raydium, using Raydium protocol to trade"
                    )
                    # Program ID should be Raydium V4 when the token is launched on Raydium
                    if program_id != RAY_V4_PROGRAM_ID:
                        logger.warning("Original transaction was on a different protocol than Raydium")
                    # assert program_id == RAY_V4_PROGRAM_ID, "Program ID must be Raydium V4"
                    # 如果 token 在 Raydium 上启动，则使用 Raydium 协议进行交易
                    #swap_event.program_id = RAY_V4_PROGRAM_ID
        except Exception as e:
            logger.exception(f"Failed to check launch status, cause: {e}")

        if should_use_pump:
            logger.info("Program ID is PUMP")
            trade_route = TradingRoute.PUMP
        # NOTE: Testing is not very ideal, use alternatives for the time being
        elif swap_event.program_id == RAY_V4_PROGRAM_ID:
            logger.info("Program ID is RayV4")
            trade_route = TradingRoute.RAYDIUM_V4
        elif program_id == METEORA_DBC_PROGRAM:
            logger.info("Program ID is Meteora DBC")
            trade_route = TradingRoute.METEORA_DBC
        elif program_id is None:
            logger.warning("Program ID is Unknown. Using Jupiter DEX aggregator to trade")
            trade_route = TradingRoute.DEX
        else:
            raise ValueError(f"Program ID is not supported, {swap_event.program_id}")

        return trade_route

    async def exec(self, swap_event: SwapEvent) -> Signature | None:
        """执行交易

        Args:
            swap_event (SwapEvent): 交易事件

        Raises:
            ConnectTimeout: If connection to the RPC node times out
            ConnectError: If connection to the RPC node fails
        """
        if swap_event.slippage_bps is not None:
            slippage_bps = swap_event.slippage_bps
        else:
            raise ValueError("slippage_bps must be specified")

        swap_direction, token_address = self._get_direction_address(swap_event)

        sig = None
        keypair = await self.__get_keypair(swap_event.user_pubkey)
        swap_in_type = SwapInType(swap_event.swap_in_type)

        if False:
            # 检查是否需要使用 Pump 协议进行交易
            should_use_pump = False
            program_id = swap_event.program_id

            try:
                is_pump_token_launched = await self._launch_cache.is_pump_token_launched(token_address)
                if program_id == PUMP_FUN_PROGRAM_ID or (
                    token_address.endswith("pump") and not is_pump_token_launched
                ):
                    should_use_pump = True
                    logger.info(
                        f"Token {token_address} is not launched on Raydium, using Pump protocol to trade"
                    )
                else:
                    logger.info(
                        f"Token {token_address} is launched on Raydium, using Raydium protocol to trade"
                    )
                    # 如果 token 在 Raydium 上启动，则使用 Raydium 协议进行交易
                    swap_event.program_id = RAY_V4_PROGRAM_ID
            except Exception as e:
                logger.exception(f"Failed to check launch status, cause: {e}")

            if should_use_pump:
                logger.info("Program ID is PUMP")
                trade_route = TradingRoute.PUMP
            # NOTE: 测试下来不是很理想，暂时使用备选方案
            elif swap_event.program_id == RAY_V4_PROGRAM_ID:
                logger.info("Program ID is RayV4")
                trade_route = TradingRoute.RAYDIUM_V4
            elif program_id is None:
                logger.warning("Program ID is Unknown, So We use thrid party to trade")
                trade_route = TradingRoute.DEX
            else:
                raise ValueError(f"Program ID is not supported, {swap_event.program_id}")
        else:
            trade_route = await self.find_route(swap_event)

        sig = await self._trading_service.use_route(trade_route).swap(
            keypair,
            token_address,
            swap_event.ui_amount,
            swap_direction,
            slippage_bps,
            swap_in_type,
            use_jito=settings.trading.use_jito,
            priority_fee=swap_event.priority_fee,
        )

        return sig

import asyncio

from aiogram.types import LinkPreviewOptions
import aioredis
from aiogram import Bot
from aiogram.enums import ParseMode

from cache.token_info import TokenInfoCache
from common.cp.swap_result import SwapResultConsumer
from common.log import logger
from common.types.swap import SwapResult
from tg_bot.services.user import UserService


_BUY_SUCCESS_TEMPLATE = """💰 ${symbol} 买入成功 🎉
{mint}

花费 {sol_ui_amount} SOL，获得 {token_ui_amount} 个 {symbol}
🔗 <a href="https://solscan.io/tx/{signature}">查看交易</a>
"""

_BUY_FAILED_TEMPLATE = """❌ ${symbol} 买入失败 😞
{mint}
"""

_SELL_SUCCESS_TEMPLATE = """💸 ${symbol} 卖出成功 ✅
{mint}

卖出 {token_ui_amount} 个 {symbol}，获得 {sol_ui_amount} SOL
🔗 <a href="https://solscan.io/tx/{signature}">查看交易</a>
"""

_SELL_FAILED_TEMPLATE = """❌ ${symbol} 卖出失败 😞
{mint}
"""


class SwapResultNotify:
    """用户交易结果通知"""

    def __init__(
        self,
        redis: aioredis.Redis,
        bot: Bot,
        batch_size: int = 10,
        poll_timeout_ms: int = 5000,
    ) -> None:
        self.redis = redis
        self.bot = bot
        self.consumer = SwapResultConsumer(
            redis_client=redis,
            consumer_group="swap_result_notify",
            consumer_name="swap_result_notify",
            batch_size=batch_size,
            poll_timeout_ms=poll_timeout_ms,
        )
        self.user_service = UserService()
        self.token_info_cache = TokenInfoCache()
        # Register the callback
        self.consumer.register_callback(self._handle_event)

    async def _build_message_for_copytrade(self, data: SwapResult) -> str:
        """构建用于跟单交易结果的消息"""
        event = data.swap_event
        if event.swap_mode == "ExactIn":
            pass
        elif event.swap_mode == "ExactOut":
            pass
        else:
            raise ValueError(f"Invalid swap_mode: {event.swap_mode}")

    async def _build_message_by_user_swap(self, data: SwapResult) -> str:
        """构建用于用户主动交易结果的消息"""
        event = data.swap_event
        swap_record = data.swap_record

        if event.swap_mode == "ExactIn":
            mint = event.output_mint
            token_info = await self.token_info_cache.get(mint)
            if token_info is None:
                raise ValueError(f"No token info found for {mint}")
            symbol = token_info.symbol

            sol_ui_amount = swap_record.input_ui_amount
            token_ui_amount = swap_record.output_ui_amount

            if swap_record is None:
                return _BUY_FAILED_TEMPLATE.format(
                    symbol=symbol,
                    mint=mint,
                )
            else:
                return _BUY_SUCCESS_TEMPLATE.format(
                    symbol=symbol,
                    sol_ui_amount=sol_ui_amount,
                    token_ui_amount=token_ui_amount,
                    mint=mint,
                    signature=data.transaction_hash,
                )
        elif event.swap_mode == "ExactOut":
            mint = event.input_mint
            token_info = await self.token_info_cache.get(mint)
            if token_info is None:
                raise ValueError(f"No token info found for {mint}")
            symbol = token_info.symbol

            if swap_record is None:
                return _SELL_FAILED_TEMPLATE.format(
                    symbol=symbol,
                    mint=mint,
                )
            else:
                token_ui_amount = swap_record.input_ui_amount
                sol_ui_amount = swap_record.output_ui_amount
                return _SELL_SUCCESS_TEMPLATE.format(
                    symbol=symbol,
                    token_ui_amount=token_ui_amount,
                    sol_ui_amount=sol_ui_amount,
                    mint=mint,
                    signature=data.transaction_hash,
                )

    async def build_message(self, data: SwapResult) -> str:
        """构建消息"""
        if data.by == "copytrade":
            return await self._build_message_for_copytrade(data)
        elif data.by == "user":
            return await self._build_message_by_user_swap(data)
        else:
            raise ValueError(f"Invalid by: {data.by}")

    async def _handle_event(self, data: SwapResult) -> None:
        try:
            logger.info(f"Handling SwapResult: {data}")
            message = await self.build_message(data)
            chat_id_list = await self.user_service.get_chat_id_by_pubkey(
                data.user_pubkey
            )

            async def _f(chat_id: int):
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(
                        is_disabled=True,
                    ),
                )

            tasks = []
            for chat_id in chat_id_list:
                tasks.append(asyncio.create_task(_f(chat_id)))
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Failed to handle event: {e}")

    async def start(self):
        """启动用户交易结果通知"""
        logger.info("Starting swap result notify")
        self._consumer_task = asyncio.create_task(self.consumer.start())

    def stop(self):
        """停止用户交易结果通知"""
        if hasattr(self, "_consumer_task"):
            self.consumer.stop()

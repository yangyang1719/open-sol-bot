import aioredis
import orjson as json
from aiogram import Bot
from aiogram.enums import ParseMode

from common.cp.swap_result import SwapResultConsumer
from common.types.swap import SwapResult
from cache.token_info import TokenInfoCache


class UserSwapResultNotify:
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
        self.token_info_cache = TokenInfoCache()
        # Register the callback
        self.consumer.register_callback(self._handle_event)

    async def _handle_event(self, data: SwapResult) -> None:
        pass

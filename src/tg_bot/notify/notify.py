import aioredis
from aiogram import Bot

from .smart_swap import SmartWalletSwapAlertNotify


class Notify:
    def __init__(self, redis: aioredis.Redis, bot: Bot):
        self.swap_notify = SmartWalletSwapAlertNotify(redis, bot)

    async def start(self):
        await self.swap_notify.start()

    async def stop(self):
        self.swap_notify.stop()

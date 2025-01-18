from typing_extensions import Self

from db.redis import RedisClient
from tg_bot.models.setting import Setting


class SettingService:
    _instance = None

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.redis = RedisClient.get_instance()
        self.channel = "setting"

    async def get(self, chat_id: int, wallet_address: str) -> Setting | None:
        data = await self.redis.get(f"setting:{chat_id}:{wallet_address}")
        if data is None:
            return None
        return Setting.from_json(data)

    async def set(self, setting: Setting):
        key = f"setting:{setting.chat_id}:{setting.wallet_address}"
        await self.redis.set(key, setting.to_json())

    async def create_default(self, chat_id: int, wallet_address: str):
        setting = Setting(
            wallet_address=wallet_address,
            chat_id=chat_id,
        )
        await self.set(setting)

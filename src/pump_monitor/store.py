import asyncio
import orjson as json
from aioredis import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from common.models.new_token import NewToken
from db.session import NEW_ASYNC_SESSION, provide_session
from .constants import NEW_TOKEN_QUEUE_KEY, PROCESSING_QUEUE_KEY, FAILED_TOKEN_QUEUE_KEY
from common.log import logger


class NewTokenStore:
    def __init__(self, redis_client: Redis):
        self._redis: Redis = redis_client
        self._running = False

    async def init(self):
        """初始化 Redis 连接"""
        self._running = True
        # 恢复处理中的消息
        await self._recover_processing_messages()
        # 恢复失败的消息
        await self._recover_failed_messages()

    async def _recover_processing_messages(self):
        """恢复处理中的消息到主队列"""
        try:
            # 获取所有处理中的消息
            while True:
                message = await self._redis.rpoplpush(
                    PROCESSING_QUEUE_KEY, NEW_TOKEN_QUEUE_KEY
                )
                if not message:
                    break
                logger.info("Recovered unprocessed message back to main queue")
        except Exception as e:
            logger.error(f"Error recovering processing messages: {e}")

    async def _recover_failed_messages(self):
        """恢复失败的消息"""
        try:
            # 获取所有失败的消息
            while True:
                message = await self._redis.rpoplpush(
                    FAILED_TOKEN_QUEUE_KEY, NEW_TOKEN_QUEUE_KEY
                )
                if not message:
                    break
                logger.info("Recovered failed message back to main queue")
        except Exception as e:
            logger.error(f"Error recovering failed messages: {e}")

    @provide_session
    async def store_new_token(
        self, token: NewToken, *, session: AsyncSession = NEW_ASYNC_SESSION
    ):
        """存储新的 token 到数据库中"""
        session.add(token)
        await session.commit()
        logger.info(f"Stored new token: {token.mint}")

    async def process_message(self, message: str):
        """处理单条消息"""
        try:
            token_data = json.loads(message)
            new_token = NewToken(**token_data)
            await self.store_new_token(new_token)
            # 处理成功后从处理中队列删除
            await self._redis.lrem(PROCESSING_QUEUE_KEY, 1, message)
            logger.info(f"Successfully processed token: {new_token.mint}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            # 处理失败，移到失败队列
            await self._redis.lpush("failed_tokens", message)
            # 从处理中队列删除
            await self._redis.lrem(PROCESSING_QUEUE_KEY, 1, message)

    async def start(self):
        """开始处理消息队列"""
        await self.init()

        logger.info("Starting token store processor...")
        while self._running:
            try:
                if not self._redis:
                    raise Exception("Redis connection is not established")

                # BRPOP 会阻塞等待直到有新消息，超时时间设为1秒
                result = await self._redis.brpop(NEW_TOKEN_QUEUE_KEY)
                if result:
                    _, message = result
                    logger.info(f"Message popped from {NEW_TOKEN_QUEUE_KEY}")

                    # 将消息放入处理中队列
                    await self._redis.lpush(PROCESSING_QUEUE_KEY, message)
                    logger.info("Message moved to processing queue")

                    # 获取当前队列长度
                    queue_length = await self._redis.llen(NEW_TOKEN_QUEUE_KEY)
                    logger.info(f"Remaining messages in queue: {queue_length}")

                    await self.process_message(message)
                else:
                    logger.info("No messages in queue")
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
                await asyncio.sleep(1)

    async def stop(self):
        """停止处理"""
        self._running = False

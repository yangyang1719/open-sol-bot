import asyncio
import websockets
from websockets.exceptions import ConnectionClosed
import orjson as json

from common.log import logger

from common.config import settings
from .constants import NEW_TOKEN_QUEUE_KEY
from aioredis import Redis


class NewTokenSubscriber:
    def __init__(self, redis_client: Redis):
        self._redis = redis_client
        self._local_queue = asyncio.Queue()
        self._sub_task = None
        self._push_task = None

    async def _push_to_redis(self):
        while 1:
            try:
                message = await self._local_queue.get()
                logger.info(f"Pushing new token to Redis: {message}")
                await self._redis.lpush(NEW_TOKEN_QUEUE_KEY, message)
            except Exception as e:
                logger.error(f"Error pushing to Redis: {e}")
                await asyncio.sleep(1)

    async def _subscribe_new_tokens(self):
        logger.info("Subscribing to new tokens...")
        while 1:
            try:
                async with websockets.connect(  # type: ignore
                    settings.api.pumpportal_api_data_url
                ) as websocket:
                    payload = {"method": "subscribeNewToken"}
                    await websocket.send(json.dumps(payload))

                    connected_message = await websocket.recv()
                    logger.info(f"Subscribed: {connected_message}")

                    async for message in websocket:
                        logger.info(f"Received new token: {message}")
                        await self._local_queue.put(message)
            except ConnectionClosed:
                logger.error("WebSocket connection closed. Retrying...")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in websocket connection: {e}")
                await asyncio.sleep(1)

    async def start(self):
        if self._sub_task is not None:
            return

        self._sub_task = asyncio.create_task(self._subscribe_new_tokens())
        self._push_task = asyncio.create_task(self._push_to_redis())

    async def stop(self):
        if self._sub_task is not None:
            self._sub_task.cancel()
            self._sub_task = None

        if self._push_task is not None:
            self._push_task.cancel()
            self._push_task = None

import asyncio
import time
from typing import Any, Callable, Coroutine, Generic, Protocol, TypeVar

import aioredis
from loguru import logger
from typing_extensions import Self


class DataProtocol(Protocol):
    def to_json(self) -> str: ...

    @classmethod
    def from_json(cls, json_str: str) -> "Self": ...


T = TypeVar("T", bound=DataProtocol)
MAX_PROCESS_TIME = 15


class Producer(Generic[T]):
    def __init__(self, redis_client: aioredis.Redis, channel: str) -> None:
        self.redis = redis_client
        self.channel = channel

    async def produce(self, data: T) -> None:
        """Produces a swap event to Redis Stream.

        Args:
            swap_event: Swap event data as string
        """
        await self.redis.xadd(
            name=self.channel,
            fields={"data": data.to_json(), "timestamp": int(time.time())},
            maxlen=10000,  # Keep last 10k events
        )


class Consumer(Generic[T]):
    def __init__(
        self,
        channel: str,
        data_class: type[T],
        redis_client: aioredis.Redis,
        consumer_group: str,
        consumer_name: str,
        batch_size: int = 10,
        poll_timeout_ms: int = 5000,
    ) -> None:
        """Initialize the transaction event consumer.

        Args:
            redis_client: Redis client instance
            consumer_group: Name of the consumer group
            consumer_name: Unique name for this consumer instance
            batch_size: Number of events to process in one batch
            poll_timeout_ms: Timeout in milliseconds for blocking read
        """
        self.channel = channel
        self.data_class = data_class
        self.redis = redis_client
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self.batch_size = batch_size
        self.poll_timeout_ms = poll_timeout_ms
        self.is_running = False
        self.callback: Callable[[T], Coroutine[Any, Any, None]] | None = None

    async def setup(self) -> None:
        """Setup the consumer group if it doesn't exist."""
        try:
            # Create consumer group if not exists
            # Use $ as start ID to only process new messages
            await self.redis.xgroup_create(
                name=self.channel,
                groupname=self.consumer_group,
                mkstream=True,
                id="$",
            )
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
            logger.info(f"Consumer group {self.consumer_group} already exists")

    def register_callback(
        self, callback: Callable[[T], Coroutine[Any, Any, None]]
    ) -> None:
        """Register a callback function to process events.

        Args:
            callback: Function that takes a dictionary of event data and processes it
        """
        self.callback = callback

    async def process_pending(self) -> None:
        """Process any pending messages for this consumer."""
        try:
            # Read pending messages from > start
            pending = await self.redis.xreadgroup(
                groupname=self.consumer_group,
                consumername=self.consumer_name,
                streams={self.channel: "0"},  # 0 means all pending messages
                count=self.batch_size,
            )

            if pending and self.callback:
                for _, messages in pending:
                    for message_id, fields in messages:
                        try:
                            await self._process_message(message_id, fields)
                        except Exception as e:
                            logger.error(
                                f"Error processing pending message {message_id}: {e}"
                            )
        except Exception as e:
            logger.error(f"Error processing pending messages: {e}")

    async def _process_message(self, message_id: str, fields: dict) -> None:
        """Process a single message and acknowledge it.

        Args:
            message_id: ID of the message in Redis Stream
            fields: Message fields containing the event data
        """
        try:
            timestamp = float(fields.get("timestamp", 0))
            if time.time() - timestamp > MAX_PROCESS_TIME:
                logger.warning(
                    f"Message {message_id} is too old, discard it. Timestamp: {timestamp}"
                )
                await self.redis.xack(self.channel, self.consumer_group, message_id)
                return
            if self.callback is not None:
                data = self.data_class.from_json(fields["data"])
                await self.callback(data)
            # Acknowledge the message
            await self.redis.xack(self.channel, self.consumer_group, message_id)
        except Exception as e:
            logger.exception(f"Error processing message {message_id}: {e}")
            # Could implement retry logic here

    async def start(self) -> None:
        """Start consuming messages from the stream."""
        if not self.callback:
            raise ValueError("No callback registered. Call register_callback first.")

        await self.setup()
        self.is_running = True

        # First process any pending messages
        await self.process_pending()

        # Then start processing new messages
        while self.is_running:
            try:
                # Read new messages
                messages = await self.redis.xreadgroup(
                    groupname=self.consumer_group,
                    consumername=self.consumer_name,
                    streams={self.channel: ">"},  # > means new messages only
                    count=self.batch_size,
                    block=self.poll_timeout_ms,
                )

                if messages:
                    for stream, stream_messages in messages:
                        for message_id, fields in stream_messages:
                            await self._process_message(message_id, fields)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error reading from stream: {e}")
                await asyncio.sleep(1)  # Avoid tight loop on errors

    def stop(self) -> None:
        """Stop consuming messages."""
        self.is_running = False


class ConsumerProducerBuilder(Generic[T]):
    def __init__(
        self,
        channel: str,
        data_class: type[T],
        redis_client: aioredis.Redis,
    ) -> None:
        self.redis = redis_client
        self.channel = channel
        self.data_class = data_class

    def build_consumer_class(
        self,
        consumer_group: str,
        consumer_name: str,
        batch_size: int = 10,
        poll_timeout_ms: int = 5000,
    ) -> Consumer[T]:
        return Consumer(
            channel=self.channel,
            data_class=self.data_class,
            redis_client=self.redis,
            consumer_group=consumer_group,
            consumer_name=consumer_name,
            batch_size=batch_size,
            poll_timeout_ms=poll_timeout_ms,
        )

    # def build_producer(self) -> Producer[T]:
    #     return Producer(redis_client=self.redis, channel=self.channel)

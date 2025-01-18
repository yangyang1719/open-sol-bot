"""交易动向通知

跟单钱包或监听钱包的交易动向通知
"""

import asyncio

import aioredis
from aiogram import Bot
from aiogram.enums import ParseMode

from common.cp.tx_event import TxEventConsumer
from common.log import logger
from common.types import TxEvent, TxType
from tg_bot.keyboards.notify_swap import notify_swap_keyboard
from tg_bot.services.monitor import MonitorService
from tg_bot.templates import render_notify_swap


class SmartWalletSwapAlertNotify:
    """聪明钱交易警告通知"""

    def __init__(
        self,
        redis: aioredis.Redis,
        bot: Bot,
        batch_size: int = 10,
        poll_timeout_ms: int = 5000,
    ) -> None:
        self.redis = redis
        self.bot = bot
        self.consumer = TxEventConsumer(
            redis_client=redis,
            consumer_group="swap_notify",
            consumer_name="swap_notify",
            batch_size=batch_size,
            poll_timeout_ms=poll_timeout_ms,
        )
        # Register the callback
        self.consumer.register_callback(self._handle_event)
        self.monitor_service = MonitorService()

    async def format_tx_message(self, tx_event: TxEvent) -> str:
        """格式化交易消息"""
        # 计算实际金额（考虑 decimals）
        from_amount = tx_event.from_amount / (10**tx_event.from_decimals)
        to_amount = tx_event.to_amount / (10**tx_event.to_decimals)
        pre_amount = tx_event.pre_token_amount / (10**tx_event.to_decimals)
        post_amount = tx_event.post_token_amount / (10**tx_event.to_decimals)

        # 计算持仓变化
        position_change = post_amount - pre_amount
        position_change_formatted = (
            f"+{position_change:.4f}"
            if position_change > 0
            else f"{position_change:.4f}"
        )

        # 计算变化百分比（仅针对加仓和减仓）
        if (
            tx_event.tx_type in [TxType.ADD_POSITION, TxType.REDUCE_POSITION]
            and pre_amount != 0
        ):
            change_percentage = (position_change / pre_amount) * 100
            percentage_str = f"({change_percentage:+.2f}%)"
            position_change_formatted = f"{position_change_formatted} {percentage_str}"

        _data = {
            TxType.OPEN_POSITION: "开仓",
            TxType.ADD_POSITION: "加仓",
            TxType.REDUCE_POSITION: "减仓",
            TxType.CLOSE_POSITION: "清仓",
        }
        # 交易类型中文映射
        tx_type_cn = _data.get(tx_event.tx_type, str(tx_event.tx_type))

        # 格式化时间
        from datetime import datetime

        tx_time = datetime.fromtimestamp(tx_event.timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # 构建消息
        message = render_notify_swap(
            tx_event=tx_event,
            from_amount=from_amount,
            to_amount=to_amount,
            tx_time=tx_time,
            tx_type_cn=tx_type_cn,
            position_change_formatted=position_change_formatted,
            post_amount=post_amount,
        )
        return message

    async def send_notification(self, tx_event: TxEvent, message: str) -> None:
        """发送通知到所有配置的聊天"""
        chat_ids = await self.monitor_service.get_chat_ids_by_target_wallet(
            str(tx_event.who)
        )
        tasks = [
            self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                reply_markup=notify_swap_keyboard(tx_event),
            )
            for chat_id in chat_ids
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error sending notifications: {e}")

    async def _handle_event(self, tx_event: TxEvent) -> None:
        """处理从Redis Stream接收到的事件

        Args:
            fields: Redis Stream消息字段
        """
        try:
            # 格式化消息
            message = await self.format_tx_message(tx_event)
            # 发送通知
            await self.send_notification(tx_event, message)
        except Exception as e:
            logger.error(f"Error handling event: {e}, raw data: {tx_event}")

    async def start(self) -> None:
        """启动通知服务"""
        logger.info("Starting transaction event notification service")
        # 使用 create_task 来启动消费者，避免阻塞
        self._consumer_task = asyncio.create_task(self.consumer.start())

    def stop(self) -> None:
        """停止通知服务"""
        if hasattr(self, "_consumer_task"):
            self._consumer_task.cancel()


#
# if __name__ == "__main__":
#     import asyncio
#     import random
#     import signal
#     import time
#
#     from aiogram import Bot, Dispatcher
#     from aiogram.filters import Command
#     from aiogram.types import Message
#
#     from common.config import settings
#
#     # 用于控制服务运行状态
#     is_running = True
#     # 存储所有需要清理的任务
#     tasks = set()
#
#     def handle_signal(signum, frame):
#         """处理系统信号"""
#         global is_running
#         print("\n收到终止信号，正在关闭服务...")
#         is_running = False
#
#     # 注册信号处理器
#     signal.signal(signal.SIGINT, handle_signal)
#     signal.signal(signal.SIGTERM, handle_signal)
#
#     async def handle_shutdown(message: Message):
#         """处理关闭命令"""
#         global is_running
#         is_running = False
#         await message.answer("正在关闭通知服务...")
#
#     async def generate_test_event():
#         """生成测试用的交易事件"""
#         # 随机选择交易类型
#         tx_type = random.choice(
#             [
#                 TxType.OPEN_POSITION,
#                 TxType.ADD_POSITION,
#                 TxType.REDUCE_POSITION,
#                 TxType.CLOSE_POSITION,
#             ]
#         )
#
#         # 基础数据
#         base_amount = random.uniform(0.1, 2.0)  # SOL数量
#         price = random.uniform(95, 105)  # USDC价格
#         usdc_amount = base_amount * price
#
#         # 持仓数据
#         if tx_type == TxType.OPEN_POSITION:
#             pre_amount = 0
#             post_amount = usdc_amount
#         elif tx_type == TxType.ADD_POSITION:
#             pre_amount = random.uniform(10, 20)
#             post_amount = pre_amount + usdc_amount
#         elif tx_type == TxType.REDUCE_POSITION:
#             pre_amount = random.uniform(20, 30)
#             post_amount = pre_amount - usdc_amount
#         else:  # CLOSE_POSITION
#             pre_amount = usdc_amount
#             post_amount = 0
#
#         # 买卖方向
#         direction = (
#             "Buy" if tx_type in [TxType.OPEN_POSITION, TxType.ADD_POSITION] else "Sell"
#         )
#
#         return TxEvent(
#             signature=hex(random.getrandbits(256))[2:],
#             from_amount=(
#                 int(base_amount * 1e9) if direction == "Buy" else int(usdc_amount * 1e6)
#             ),
#             from_decimals=9 if direction == "Buy" else 6,
#             to_amount=(
#                 int(usdc_amount * 1e6) if direction == "Buy" else int(base_amount * 1e9)
#             ),
#             to_decimals=6 if direction == "Buy" else 9,
#             mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
#             who="5ZWj7a1f8tWkjBESHKgrLmXshuXxqeY9SYcfbshpAqPG",
#             tx_type=tx_type,
#             tx_direction=direction,
#             timestamp=int(time.time()),
#             pre_token_amount=int(pre_amount * 1e6),
#             post_token_amount=int(post_amount * 1e6),
#         )
#
#     async def simulate_events(notify: SwapNotify):
#         """模拟生成交易事件并发送通知"""
#         print("开始生成测试数据...")
#         while is_running:
#             try:
#                 event = await generate_test_event()
#                 message = await notify.format_tx_message(event)
#                 for chat_id in notify.notify_chat_ids:
#                     await notify.send_notification(
#                         tx_event=event,
#                         message=message,
#                     )
#                 print(f"已发送 {event.tx_type.value} 事件通知")
#             except Exception as e:
#                 logger.error(f"发送通知失败: {e}")
#
#             if not is_running:
#                 break
#
#             # 随机等待5-15秒后发送下一条
#             try:
#                 await asyncio.sleep(random.uniform(5, 15))
#             except asyncio.CancelledError:
#                 break
#
#     async def main():
#         redis = None
#         bot = None
#         notify = None
#
#         try:
#             # 创建 Redis 客户端
#             redis = aioredis.Redis.from_url("redis://localhost/1")
#
#             # 创建 Bot 和 Dispatcher
#             bot = Bot(token=settings.tg_bot.token)
#             dp = Dispatcher()
#
#             # 注册 shutdown 命令处理器
#             dp.message.register(handle_shutdown, Command("shutdown"))
#
#             # 创建通知服务实例
#             notify = SwapNotify(
#                 redis=redis,
#                 bot=bot,
#                 notify_chat_ids=[5049063827],  # 你的 chat ID
#             )
#
#             # 启动通知服务
#             await notify.start()
#             print("通知服务已启动。发送 /shutdown 命令来停止服务。")
#             print("按 Ctrl+C 可以随时停止服务。")
#
#             # 创建并存储任务
#             polling_task = asyncio.create_task(dp.start_polling(bot))
#             simulate_task = asyncio.create_task(simulate_events(notify))
#             tasks.add(polling_task)
#             tasks.add(simulate_task)
#
#             # 等待任务完成或被取消
#             done, pending = await asyncio.wait(
#                 {polling_task, simulate_task}, return_when=asyncio.FIRST_COMPLETED
#             )
#
#             # 取消剩余的任务
#             for task in pending:
#                 task.cancel()
#                 try:
#                     await task
#                 except asyncio.CancelledError:
#                     pass
#
#         except asyncio.CancelledError:
#             print("\n服务被取消")
#         except Exception as e:
#             logger.error(f"服务异常: {e}")
#             raise
#         finally:
#             # 清理所有任务
#             for task in tasks:
#                 if not task.done():
#                     task.cancel()
#                     try:
#                         await task
#                     except asyncio.CancelledError:
#                         pass
#
#             # 清理资源
#             if notify:
#                 notify.stop()
#             if redis:
#                 await redis.close()
#             if bot:
#                 await bot.session.close()
#             print("通知服务已关闭。")
#
#     # 运行服务
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         pass  # 已经在信号处理器中处理了
#     except Exception as e:
#         logger.error(f"服务异常终止: {e}")
#         logger.exception(e)

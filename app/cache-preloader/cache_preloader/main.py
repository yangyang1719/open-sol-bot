import asyncio
import signal

from common.log import logger
from common.prestart import pre_start

from cache_preloader.services.auto_update_service import AutoUpdateCacheService


async def main():
    """主函数"""
    pre_start()

    service = AutoUpdateCacheService()

    def signal_handler():
        """信号处理函数"""
        logger.info("Received shutdown signal")
        # 使用 create_task 来避免阻塞信号处理
        asyncio.create_task(service.stop())

    # 注册信号处理
    loop = asyncio.get_running_loop()

    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

        # 启动服务并等待结束
        await service.start()
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        raise
    finally:
        # 移除信号处理器
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(sig)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

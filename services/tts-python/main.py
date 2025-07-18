import asyncio
import signal
import os
from tts_service import TTSService

async def main():
    """
    运行 TTS 服务的主函数。
    """
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    service = TTSService(config_path)

    loop = asyncio.get_running_loop()
    
    # 创建一个 future 用于等待关闭信号
    stop_event = asyncio.Future()

    # 处理优雅关闭
    def handle_shutdown(s):
        print(f"接收到退出信号 {s.name}...")
        asyncio.create_task(shutdown(s, service, stop_event))

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_shutdown, sig)

    # 启动服务
    await service.start()
    
    try:
        # 等待直到接收到关闭信号
        await stop_event
    except asyncio.CancelledError:
        pass
    finally:
        # 最终清理
        if not service.task.done():
             # 给关闭操作一点时间来完成
            await asyncio.sleep(1)
        print("主函数退出。")


async def shutdown(signal, service: TTSService, stop_event: asyncio.Future):
    """
    处理关闭序列。
    """
    if service._running:
        await service.stop()
        
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        print(f"正在取消 {len(tasks)} 个未完成的任务...")
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    # 通知主循环退出
    if not stop_event.done():
        stop_event.set_result(True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("TTS 服务已关闭。")
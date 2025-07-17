import asyncio
import signal
import os
from tts_service import TTSService

async def main():
    """
    Main function to run the TTS service.
    """
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    service = TTSService(config_path)

    loop = asyncio.get_running_loop()
    
    # Handle graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s, service))
        )

    await service.start()

async def shutdown(signal, service: TTSService):
    """
    Handles the shutdown sequence.
    """
    print(f"Received exit signal {signal.name}...")
    await service.stop()
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    asyncio.get_running_loop().stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("TTS Service shut down.")

import asyncio
import os
import sys
import threading
import time

import pytest
import pytest_asyncio
import uvicorn
import websockets

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import main  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


async def _backend_handler(websocket, path):
    """Simple mock backend server handling input and output routes."""
    try:
        while True:
            message = await websocket.recv()
            if path == "/ws/input":
                await websocket.send(f"Echo: {message}")
            elif path.startswith("/ws/output/"):
                await websocket.send(f"Output: {message}")
    except websockets.exceptions.ConnectionClosed:
        pass


@pytest.fixture(scope="session")
def mock_backend_server():
    """启动模拟后端服务"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    server = loop.run_until_complete(
        websockets.serve(_backend_handler, "127.0.0.1", 8001)
    )

    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    yield "ws://127.0.0.1:8001"

    loop.call_soon_threadsafe(server.close)
    loop.call_soon_threadsafe(loop.stop)
    thread.join()


def run_server(server):
    """在新线程中运行服务器"""
    try:
        server.run()
    except SystemExit:
        pass


@pytest.fixture(scope="session")
def gateway_server():
    """启动网关服务"""
    os.environ["INPUT_HANDLER_URL"] = "ws://127.0.0.1:8001"
    os.environ["OUTPUT_HANDLER_URL"] = "ws://127.0.0.1:8001"
    main.BACKEND_SERVICES["input"] = os.environ["INPUT_HANDLER_URL"]
    main.BACKEND_SERVICES["output"] = os.environ["OUTPUT_HANDLER_URL"]

    config = uvicorn.Config(
        main.app,
        host="127.0.0.1",
        port=8000,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()
    time.sleep(1)

    yield "ws://127.0.0.1:8000"

    server.should_exit = True
    thread.join()
    if "INPUT_HANDLER_URL" in os.environ:
        del os.environ["INPUT_HANDLER_URL"]
    if "OUTPUT_HANDLER_URL" in os.environ:
        del os.environ["OUTPUT_HANDLER_URL"]

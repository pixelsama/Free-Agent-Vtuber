import os
import sys
import pytest
import pytest_asyncio
import asyncio
import websockets
from fastapi import FastAPI
import uvicorn
import threading
import time
from contextlib import asynccontextmanager

# 检查是否可以导入TestClient
try:
    from fastapi.testclient import TestClient
    HAS_TEST_CLIENT = True
except ImportError:
    TestClient = None
    HAS_TEST_CLIENT = False

# 将当前目录添加到Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 导入main模块
import main


# 用于存储运行中的服务器信息
class ServerInfo:
    def __init__(self):
        self.should_exit = False
        self.thread = None


# 创建一个简单的后端服务模拟器
@asynccontextmanager
async def mock_backend_lifespan(app: FastAPI):
    yield
    # 关闭时执行的清理代码


mock_backend_app = FastAPI(lifespan=mock_backend_lifespan)


@mock_backend_app.websocket("/ws/input")
async def mock_input_websocket(websocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            # 回显消息
            await websocket.send_text(f"Echo: {message}")
    except websockets.exceptions.ConnectionClosed:
        pass


@mock_backend_app.websocket("/ws/output/{task_id}")
async def mock_output_websocket(websocket, task_id: str):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            # 回显消息
            await websocket.send_text(f"Output: {message}")
    except websockets.exceptions.ConnectionClosed:
        pass


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def mock_backend_server():
    """启动模拟后端服务"""
    config = uvicorn.Config(
        mock_backend_app,
        host="127.0.0.1",
        port=8001,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    
    # 在单独的线程中运行服务器
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()
    
    # 等待服务器启动
    time.sleep(1)
    
    yield "ws://127.0.0.1:8001"
    
    # 停止服务器
    server.should_exit = True
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
    # 设置环境变量以指向模拟的后端服务
    os.environ["INPUT_HANDLER_URL"] = "ws://127.0.0.1:8001"
    os.environ["OUTPUT_HANDLER_URL"] = "ws://127.0.0.1:8001"
    
    config = uvicorn.Config(
        main.app,
        host="127.0.0.1",
        port=8000,
        log_level="warning"
    )
    server = uvicorn.Server(config)
    
    # 在单独的线程中运行服务器
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()
    
    # 等待服务器启动
    time.sleep(1)
    
    yield "ws://127.0.0.1:8000"
    
    # 停止服务器
    server.should_exit = True
    thread.join()
    
    # 清理环境变量
    if "INPUT_HANDLER_URL" in os.environ:
        del os.environ["INPUT_HANDLER_URL"]
    if "OUTPUT_HANDLER_URL" in os.environ:
        del os.environ["OUTPUT_HANDLER_URL"]

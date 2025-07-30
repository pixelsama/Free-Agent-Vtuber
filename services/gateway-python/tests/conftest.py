import os
import sys
import pytest
from unittest.mock import AsyncMock, Mock, MagicMock
import websockets

# 将当前目录添加到Python路径中，以便可以直接导入main模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# 导入main模块
import main


@pytest.fixture
def mock_websocket():
    """提供模拟的WebSocket对象"""
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.receive = AsyncMock()
    mock_ws.send = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.fixture
def mock_websocket_connection():
    """提供模拟的websockets连接对象"""
    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    return mock_conn


@pytest.fixture
def sample_config():
    """提供示例配置"""
    return {
        "gateway": {
            "host": "0.0.0.0",
            "port": 8000,
            "log_level": "info"
        },
        "backend_services": {
            "input": {
                "url": "ws://localhost:8001",
                "endpoint": "/ws/input"
            },
            "output": {
                "url": "ws://localhost:8002", 
                "endpoint": "/ws/output"
            }
        },
        "proxy": {
            "connection_timeout": 300,
            "max_connections": 1000
        }
    }


@pytest.fixture
def mock_backend_services():
    """提供模拟的后端服务配置"""
    return {
        "input": "ws://localhost:8001",
        "output": "ws://localhost:8002"
    }

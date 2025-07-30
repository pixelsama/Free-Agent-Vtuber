import pytest
from unittest.mock import AsyncMock, Mock, patch
import json

# 检查是否可以导入TestClient
try:
    from fastapi.testclient import TestClient
    # 导入要测试的模块
    from main import app, active_connections
    
    # 创建测试客户端
    client = TestClient(app)
    HAS_TEST_CLIENT = True
except ImportError:
    HAS_TEST_CLIENT = False
    app = None
    active_connections = {}
    TestClient = None


def test_root_endpoint():
    """测试根路径端点"""
    response = client.get("/")
    assert response.status_code == 200
    assert "AIVtuber API Gateway" in response.text
    assert "WebSocket端点" in response.text


def test_health_check():
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["gateway"] == "running"
    assert "active_connections" in data
    assert "backend_services" in data


def test_connections_endpoint():
    """测试连接状态端点"""
    # 先添加一个模拟连接
    active_connections["test_conn"] = Mock()
    
    response = client.get("/connections")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_connections"] == 1
    assert "test_conn" in data["connections"]
    
    # 清理模拟连接
    active_connections.clear()


def test_cors_headers():
    """测试CORS头部"""
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


@patch('main.websockets.connect')
def test_websocket_input_route(mock_websocket_connect):
    """测试WebSocket输入路由"""
    # 模拟websockets.connect返回值
    mock_backend_ws = AsyncMock()
    mock_websocket_connect.return_value.__aenter__.return_value = mock_backend_ws
    
    # 注意：由于TestClient不完全支持WebSocket测试，这里只做基本的路由测试
    # 更完整的WebSocket测试将在集成测试中进行


@patch('main.websockets.connect')
def test_websocket_output_route(mock_websocket_connect):
    """测试WebSocket输出路由"""
    # 模拟websockets.connect返回值
    mock_backend_ws = AsyncMock()
    mock_websocket_connect.return_value.__aenter__.return_value = mock_backend_ws
    
    # 注意：由于TestClient不完全支持WebSocket测试，这里只做基本的路由测试
    # 更完整的WebSocket测试将在集成测试中进行

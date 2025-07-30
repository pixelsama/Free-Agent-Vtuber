import pytest
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


def test_health_check_endpoint():
    """测试健康检查端点的详细内容"""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["gateway"] == "running"
    assert isinstance(data["active_connections"], int)
    assert "backend_services" in data
    
    # 验证后端服务配置格式
    backend_services = data["backend_services"]
    assert "input" in backend_services
    assert "output" in backend_services


def test_health_check_response_headers():
    """测试健康检查端点的响应头部"""
    response = client.get("/health")
    assert response.status_code == 200
    
    # 检查Content-Type头部
    assert response.headers["content-type"] == "application/json"


def test_health_check_with_active_connections():
    """测试有活跃连接时的健康检查"""
    # 添加一些模拟连接
    active_connections["input_1"] = "mock_websocket_1"
    active_connections["output_1"] = "mock_websocket_2"
    
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["active_connections"] == 2
    
    # 清理模拟连接
    active_connections.clear()


def test_connections_endpoint_structure():
    """测试连接端点返回的数据结构"""
    # 添加一些模拟连接
    active_connections["input_1"] = "mock_websocket_1"
    active_connections["output_2"] = "mock_websocket_2"
    
    response = client.get("/connections")
    assert response.status_code == 200
    
    data = response.json()
    assert "total_connections" in data
    assert "connections" in data
    assert isinstance(data["total_connections"], int)
    assert isinstance(data["connections"], list)
    
    # 验证连接数量
    assert data["total_connections"] == 2
    assert len(data["connections"]) == 2
    
    # 验证连接ID格式
    for conn_id in data["connections"]:
        assert isinstance(conn_id, str)
        assert "_" in conn_id  # 应该包含类型和ID，如 "input_1"
    
    # 清理模拟连接
    active_connections.clear()


def test_empty_connections():
    """测试没有连接时的连接端点"""
    # 确保没有活跃连接
    active_connections.clear()
    
    response = client.get("/connections")
    assert response.status_code == 200
    
    data = response.json()
    assert data["total_connections"] == 0
    assert data["connections"] == []

import pytest
from fastapi.testclient import TestClient

from main import active_connections, app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check_endpoint(client):
    """测试健康检查端点的详细内容"""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert data["gateway"] == "running"
    assert isinstance(data["active_connections"], int)
    assert "backend_services" in data

    backend_services = data["backend_services"]
    assert "input" in backend_services
    assert "output" in backend_services


def test_health_check_response_headers(client):
    """测试健康检查端点的响应头部"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"


def test_health_check_with_active_connections(client):
    """测试有活跃连接时的健康检查"""
    active_connections["input_1"] = "mock_websocket_1"
    active_connections["output_1"] = "mock_websocket_2"

    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["active_connections"] == 2

    active_connections.clear()


def test_connections_endpoint_structure(client):
    """测试连接端点返回的数据结构"""
    active_connections["input_1"] = "mock_websocket_1"
    active_connections["output_2"] = "mock_websocket_2"

    response = client.get("/connections")
    assert response.status_code == 200

    data = response.json()
    assert "total_connections" in data
    assert "connections" in data
    assert isinstance(data["total_connections"], int)
    assert isinstance(data["connections"], list)
    assert data["total_connections"] == 2
    assert len(data["connections"]) == 2
    for conn_id in data["connections"]:
        assert isinstance(conn_id, str)
        assert "_" in conn_id

    active_connections.clear()


def test_empty_connections(client):
    """测试没有连接时的连接端点"""
    active_connections.clear()

    response = client.get("/connections")
    assert response.status_code == 200

    data = response.json()
    assert data["total_connections"] == 0
    assert data["connections"] == []

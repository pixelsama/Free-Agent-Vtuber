from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from main import active_connections, app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_root_endpoint(client):
    """测试根路径端点"""
    response = client.get("/")
    assert response.status_code == 200
    assert "AIVtuber API Gateway" in response.text
    assert "WebSocket端点" in response.text


def test_health_check(client):
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["gateway"] == "running"
    assert "active_connections" in data
    assert "backend_services" in data


def test_connections_endpoint(client):
    """测试连接状态端点"""
    active_connections["test_conn"] = Mock()
    response = client.get("/connections")
    assert response.status_code == 200
    data = response.json()
    assert data["total_connections"] == 1
    assert "test_conn" in data["connections"]
    active_connections.clear()


def test_cors_headers(client):
    """测试CORS头部"""
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

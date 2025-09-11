import json
import os
import types

import pytest
from fastapi.testclient import TestClient

# 注意：测试在模块目录下运行：cd services/gateway-python && pytest
import importlib

@pytest.fixture()
def app():
    # 动态导入 main.py 内的 FastAPI app（已挂载 /api）
    main = importlib.import_module("main")
    return main.app

@pytest.fixture()
def client(app):
    return TestClient(app)

def test_asr_route_requires_absolute_path(client, monkeypatch):
    # 传递相对路径应报 400
    resp = client.post("/api/asr", json={"path": "relative.wav"})
    assert resp.status_code == 400
    data = resp.json()
    assert "path must be absolute" in data.get("error", "")

def test_asr_route_pushes_to_redis_list(client, monkeypatch):
    # 准备一个假的 Redis 客户端来捕获 lpush 调用
    pushed = []

    class DummyRedis:
        async def lpush(self, queue, message):
            pushed.append((queue, message))

    # 替换 asr_routes.get_redis 返回 DummyRedis
    asr_routes = importlib.import_module("src.services.asr_routes")
    monkeypatch.setattr(asr_routes, "get_redis", lambda: DummyRedis())

    abs_path = "/tmp/file.wav"
    resp = client.post("/api/asr", json={"path": abs_path, "options": {"lang": "zh"}})
    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data

    # 验证写入了正确的队列与消息格式
    assert len(pushed) == 1
    queue, message = pushed[0]
    assert queue == os.environ.get("ASR_TASKS_QUEUE", "asr_tasks")

    msg = json.loads(message)
    assert msg["audio"]["type"] == "file"
    assert msg["audio"]["path"] == abs_path
    assert msg["audio"]["format"] == "wav"
    assert msg["options"]["lang"] == "zh"
    assert msg["meta"]["source"] == "gateway"

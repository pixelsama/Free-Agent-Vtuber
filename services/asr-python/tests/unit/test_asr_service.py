import asyncio
import json
import os
import sys
from typing import Any, Dict

import pytest

# 以模块目录为根运行测试：pytest 从 services/asr-python 执行
# 从包内模块导入（Phase 2 重构后）
from asr_service import RedisClient, worker_loop
from providers.factory import FakeProvider, build_provider

@pytest.mark.asyncio
async def test_build_provider_fake():
    provider = build_provider("fake", {"credentials": {}})
    assert isinstance(provider, FakeProvider)

@pytest.mark.asyncio
async def test_worker_loop_with_fake_provider(monkeypatch):
    """
    验证：从队列取到一条 file 类型任务，调用 FakeProvider，最终向结果频道发布 finished 消息。
    使用内存桩替代 RedisClient 的网络调用。
    """

    # 内存桩：捕获发布的消息
    published: list[str] = []
    tasks: list[str] = []

    class DummyRedis(RedisClient):  # type: ignore
        def __init__(self):
            pass

        async def blpop(self, queue: str, timeout: int = 1):
            try:
                return tasks.pop(0)
            except IndexError:
                await asyncio.sleep(0.01)
                return None

        async def publish(self, channel: str, message: str):
            published.append(message)

        async def lpush(self, queue: str, message: str):
            tasks.insert(0, message)

        async def close(self):
            return

    redis_client = DummyRedis()
    provider = FakeProvider()

    # 准备任务
    task_id = "t-123"
    msg: Dict[str, Any] = {
        "task_id": task_id,
        "audio": {
            "type": "file",
            "path": "/abs/path/to/file.wav",
            "format": "wav",
            "sample_rate": 16000,
            "channels": 1,
        },
        "options": {
            "lang": "zh",
            "timestamps": True,
            "diarization": False,
        },
        "meta": {"source": "test"},
    }
    await redis_client.lpush("asr_tasks", json.dumps(msg, ensure_ascii=False))

    # 启动单个 worker，跑一小段时间后取消
    task = asyncio.create_task(
        worker_loop("W1", redis_client, "asr_tasks", "asr_results", provider, timeout_sec=3)
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # 校验发布结果
    assert len(published) >= 1
    # 取最后一条
    result = json.loads(published[-1])
    assert result["task_id"] == task_id
    assert result["status"] == "finished"
    assert result["text"] == "测试文本"
    assert result["provider"] == "fake"
    assert result["lang"] == "zh"

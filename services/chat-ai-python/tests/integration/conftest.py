import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pytest
import pytest_asyncio

# 集成测试的共享fixtures


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@dataclass
class InMemoryPubSub:
    """简单的内存版Pub/Sub实现"""

    _store: "InMemoryRedis"
    channel: Optional[str] = None
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)

    async def subscribe(self, channel: str) -> None:
        self.channel = channel
        self._store._subscribers.setdefault(channel, []).append(self.queue)
        await self.queue.put({"type": "subscribe", "channel": channel})

    async def unsubscribe(self, channel: str) -> None:
        queues = self._store._subscribers.get(channel, [])
        if self.queue in queues:
            queues.remove(self.queue)

    async def get_message(self, timeout: Optional[float] = None):
        try:
            return await asyncio.wait_for(self.queue.get(), timeout)
        except asyncio.TimeoutError:
            return None

    async def close(self) -> None:
        if self.channel:
            await self.unsubscribe(self.channel)


@dataclass
class InMemoryRedis:
    """极简内存版Redis，仅支持测试所需命令"""

    data: Dict[str, List[str]] = field(default_factory=dict)
    _subscribers: Dict[str, List[asyncio.Queue]] = field(default_factory=dict)

    async def ping(self) -> bool:
        return True

    async def flushdb(self) -> None:
        self.data.clear()
        self._subscribers.clear()

    async def close(self) -> None:
        pass

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)

    async def lpush(self, key: str, value: str) -> None:
        self.data.setdefault(key, []).insert(0, value)

    async def llen(self, key: str) -> int:
        return len(self.data.get(key, []))

    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        lst = self.data.get(key, [])
        if end == -1:
            end = len(lst)
        else:
            end += 1
        return lst[start:end]

    async def publish(self, channel: str, message: str) -> int:
        queues = self._subscribers.get(channel, [])
        for q in queues:
            await q.put({"type": "message", "channel": channel, "data": message})
        return len(queues)

    def pubsub(self) -> InMemoryPubSub:
        return InMemoryPubSub(self)


@pytest_asyncio.fixture
async def redis_client():
    """提供测试用的内存Redis客户端"""
    client = InMemoryRedis()
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()


@pytest.fixture
def test_config():
    """测试配置"""
    return {
        "ai": {
            "provider": "openai_compatible",
            "api_base": "https://test-api.example.com/v1",
            "api_key": "test-key",
            "model": "test-model",
            "max_tokens": 100,
            "temperature": 0.7,
            "timeout": 30,
            "max_retries": 3,
            "system_prompt": "你是一个测试AI助手",
            "fallback_to_rules": True,
        },
        "redis": {"host": "localhost", "port": 6379},
        "processing": {
            "max_concurrent_tasks": 10,
            "task_timeout": 60,
            "response_delay": 0.1,
        },
    }

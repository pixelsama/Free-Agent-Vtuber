import json
import os
import pytest
import redis.asyncio as redis
import asyncio
from pathlib import Path

# 集成测试的共享fixtures


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def redis_url():
    """Redis连接URL"""
    return os.getenv("REDIS_URL", "redis://localhost:6379/15")


@pytest.fixture
async def redis_client(redis_url):
    """提供测试用的Redis客户端"""
    client = redis.Redis.from_url(redis_url, decode_responses=True)
    try:
        await client.ping()
        # 清理测试数据库
        await client.flushdb()
        yield client
    finally:
        # 清理测试数据库
        await client.flushdb()
        await client.close()


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
            "fallback_to_rules": True
        },
        "redis": {
            "host": "localhost",
            "port": 6379
        },
        "processing": {
            "max_concurrent_tasks": 10,
            "task_timeout": 60,
            "response_delay": 0.1
        }
    }

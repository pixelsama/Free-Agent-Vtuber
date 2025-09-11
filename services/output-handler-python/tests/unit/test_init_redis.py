import pytest

import main as main_module


class DummyRedis:
    async def ping(self):
        return True

    async def close(self):
        return True


@pytest.mark.asyncio
async def test_init_redis(monkeypatch):
    monkeypatch.setattr(main_module.redis, "Redis", lambda *a, **k: DummyRedis())
    await main_module.init_redis()
    assert main_module.redis_client is not None
    await main_module.cleanup_redis()

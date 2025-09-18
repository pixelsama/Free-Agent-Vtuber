import importlib
import pytest


class DummyRedis:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.fail_after = fail_after
        self.calls: list[tuple[str, dict]] = []

    async def xadd(self, stream, fields, maxlen=None, approximate=None):  # type: ignore[override]
        self.calls.append((stream, dict(fields)))
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise RuntimeError("xadd failure")
        return "ok"


@pytest.fixture()
def outbox(monkeypatch, tmp_path):
    db_path = tmp_path / "outbox.sqlite"
    monkeypatch.setenv("DIALOG_ENGINE_DB", str(db_path))
    from dialog_engine import ltm_outbox as module

    yield importlib.reload(module)


@pytest.mark.asyncio
async def test_flush_once_marks_delivered(outbox):
    outbox.add_event("LtmWriteRequested", {"foo": "bar"})
    outbox.add_event("AnalyticsChatStats", {"foo": "baz"})

    redis_stub = DummyRedis()
    flushed = await outbox._flush_once(redis_stub)

    assert flushed == 2
    assert [stream for stream, _ in redis_stub.calls] == ["events.ltm", "events.analytics"]
    # After flush, there should be no pending events left in the database
    assert outbox._fetch_batch() == []


@pytest.mark.asyncio
async def test_flush_stops_on_first_failure(outbox):
    outbox.add_event("LtmWriteRequested", {"foo": "bar"})
    outbox.add_event("AnalyticsChatStats", {"foo": "baz"})

    redis_stub = DummyRedis(fail_after=1)
    flushed = await outbox._flush_once(redis_stub)

    assert flushed == 0
    # Since first insert failed, both items remain pending
    pending = outbox._fetch_batch()
    assert len(pending) == 2

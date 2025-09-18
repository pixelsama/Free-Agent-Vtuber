import asyncio

import pytest

from dialog_engine.tts_providers.mock import MockTtsProvider

try:
    from dialog_engine.tts_providers.edge_tts_provider import EdgeTtsProvider
except RuntimeError:
    EdgeTtsProvider = None


def _skip_edge():
    return pytest.mark.skipif(EdgeTtsProvider is None, reason="edge-tts dependency unavailable")


@pytest.mark.asyncio
async def test_mock_provider_respects_stop_event():
    provider = MockTtsProvider(chunk_delay_ms=1, chunk_count=5)
    stop_event = asyncio.Event()
    chunks = []
    async for chunk in provider.stream(session_id="s", text="hello", stop_event=stop_event):
        chunks.append(chunk)
        stop_event.set()
    assert len(chunks) == 1


@_skip_edge()
@pytest.mark.asyncio
async def test_edge_provider_stream(monkeypatch):
    emitted = [b"chunk1", b"chunk2"]

    class DummyStream:
        def __init__(self):
            self._iter = iter([
                {"type": "audio", "data": emitted[0]},
                {"type": "non-audio"},
                {"type": "audio", "data": emitted[1]},
            ])

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def aclose(self):
            return None

    class DummyCommunicate:
        def __init__(self, *args, **kwargs):
            self.stopped = False

        def stream(self):
            return DummyStream()

        async def stop(self):
            self.stopped = True

    monkeypatch.setattr(
        "dialog_engine.tts_providers.edge_tts_provider.edge_tts.Communicate",
        DummyCommunicate,
    )

    provider = EdgeTtsProvider(voice="zh-CN-XiaoxiaoNeural")
    stop_event = asyncio.Event()
    collected = []
    async for chunk in provider.stream(session_id="s", text="你好", stop_event=stop_event):
        collected.append(chunk)
        if len(collected) == 1:
            stop_event.set()
    assert collected == [emitted[0]]

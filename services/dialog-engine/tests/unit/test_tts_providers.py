import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


_BASE_DIR = Path(__file__).resolve().parents[2] / "tts_providers"
_PACKAGE_NAME = "dialog_engine_tts_testpkg"

pkg = sys.modules.setdefault(_PACKAGE_NAME, types.ModuleType(_PACKAGE_NAME))
pkg.__path__ = [str(_BASE_DIR)]  # type: ignore[attr-defined]


def _load_module(module_name: str):
    full_name = f"{_PACKAGE_NAME}.{module_name}"
    existing = sys.modules.get(full_name)
    if existing:
        return existing

    module_path = _BASE_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    module.__package__ = _PACKAGE_NAME
    sys.modules[full_name] = module
    setattr(pkg, module_name, module)
    spec.loader.exec_module(module)
    return module


_base_module = _load_module("base")
_mock_module = _load_module("mock")
MockTtsProvider = _mock_module.MockTtsProvider

try:
    _edge_module = _load_module("edge_tts_provider")
    EdgeTtsProvider = _edge_module.EdgeTtsProvider
except RuntimeError:
    _edge_module = None
    EdgeTtsProvider = None


@pytest.mark.asyncio
async def test_mock_provider_respects_stop_event():
    provider = MockTtsProvider(chunk_delay_ms=1, chunk_count=5)
    stop_event = asyncio.Event()
    chunks = []
    async for chunk in provider.stream(session_id="s", text="hello", stop_event=stop_event):
        chunks.append(chunk)
        stop_event.set()
    assert len(chunks) == 1


@pytest.mark.asyncio
@pytest.mark.skipif(EdgeTtsProvider is None, reason="edge-tts dependency unavailable")
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
            except StopIteration:
                raise StopAsyncIteration

        async def aclose(self):
            return None

    class DummyCommunicate:
        def __init__(self, *args, **kwargs):
            self.stopped = False

        def stream(self):
            return DummyStream()

        async def stop(self):
            self.stopped = True

    monkeypatch.setattr(_edge_module.edge_tts, "Communicate", DummyCommunicate)

    provider = EdgeTtsProvider(voice="zh-CN-XiaoxiaoNeural")
    stop_event = asyncio.Event()
    collected = []
    async for chunk in provider.stream(session_id="s", text="你好", stop_event=stop_event):
        collected.append(chunk)
        if len(collected) == 1:
            stop_event.set()
    assert collected == [emitted[0]]

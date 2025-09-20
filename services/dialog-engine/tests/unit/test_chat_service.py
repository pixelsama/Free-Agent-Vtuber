import asyncio
from typing import Iterable, List

import pytest

from dialog_engine.chat_service import ChatService
from dialog_engine.settings import LLMSettings, OpenAISettings, Settings


def _make_settings(*, enabled: bool) -> Settings:
    return Settings(
        openai=OpenAISettings(api_key=None, organization=None, base_url=None),
        llm=LLMSettings(
            enabled=enabled,
            model="dummy",
            temperature=0.0,
            max_tokens=128,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            timeout=1.0,
            retry_limit=0,
            retry_backoff_seconds=0.0,
        ),
    )


class _StubLLMClient:
    def __init__(self, responses: Iterable[str]) -> None:
        self._responses = list(responses)
        self.calls: List[list[dict[str, str]]] = []

    async def stream_chat(self, messages, **kwargs):
        self.calls.append(list(messages))
        for token in self._responses:
            await asyncio.sleep(0)
            yield token


class _FailingLLMClient:
    async def stream_chat(self, messages, **kwargs):
        if False:
            yield ""  # pragma: no cover - ensure object is async generator
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_stream_reply_mock_path():
    service = ChatService(settings=_make_settings(enabled=False))

    chunks = []
    async for delta in service.stream_reply("session", "你好", meta={"lang": "zh"}):
        chunks.append(delta)

    text = "".join(chunks).strip()
    assert "你说「你好」" in text
    assert service.last_source == "mock"
    assert service.last_ttft_ms is not None
    assert service.last_token_count > 0
    assert service.last_error is None


@pytest.mark.asyncio
async def test_stream_reply_llm_path():
    stub = _StubLLMClient(["Hello", " world"])
    service = ChatService(
        settings=_make_settings(enabled=True),
        llm_client_factory=lambda: stub,
    )

    chunks = []
    async for delta in service.stream_reply("live-1", "hello", meta={}):
        chunks.append(delta)

    assert "".join(chunks) == "Hello world"
    assert service.last_source == "llm"
    assert service.last_token_count >= 2
    assert stub.calls
    assert stub.calls[0][-1]["content"] == "hello"


@pytest.mark.asyncio
async def test_stream_reply_llm_failure_fallback():
    service = ChatService(
        settings=_make_settings(enabled=True),
        llm_client_factory=_FailingLLMClient,
    )

    chunks = []
    async for delta in service.stream_reply("live-err", "test", meta={"lang": "en"}):
        chunks.append(delta)

    assert "You said: 'test'" in "".join(chunks)
    assert service.last_source == "mock"
    assert service.last_error == "RuntimeError"
    assert service.last_token_count > 0

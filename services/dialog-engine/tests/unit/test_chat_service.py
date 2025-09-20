import asyncio
from typing import Iterable, List, Optional

import pytest

from dialog_engine.chat_service import ChatService
from dialog_engine.memory_store import MemoryTurn
from dialog_engine.settings import (
    LLMSettings,
    LTMInlineSettings,
    OpenAISettings,
    Settings,
    ShortTermMemorySettings,
)


def _make_settings(
    *,
    enabled: bool,
    stm_enabled: bool = False,
    ltm_enabled: bool = False,
    base_url: Optional[str] = None,
) -> Settings:
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
        short_term=ShortTermMemorySettings(
            enabled=stm_enabled,
            db_path=":memory:",
            context_turns=5,
        ),
        ltm_inline=LTMInlineSettings(
            enabled=ltm_enabled,
            base_url=base_url,
            retrieve_path="/ltm",
            timeout=1.0,
            max_snippets=3,
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


class _StubMemoryStore:
    def __init__(self, turns: Iterable[MemoryTurn]) -> None:
        self.turns = list(turns)
        self.calls: List[tuple[str, Optional[int]]] = []

    async def fetch_recent(self, session_id: str, limit: Optional[int] = None):
        self.calls.append((session_id, limit))
        return list(self.turns)


class _StubLTMClient:
    def __init__(self, snippets: Iterable[str]) -> None:
        self.snippets = list(snippets)
        self.calls: List[tuple[str, str, dict]] = []

    def is_configured(self) -> bool:
        return True

    async def retrieve(self, *, session_id: str, user_text: str, meta, limit=None):
        self.calls.append((session_id, user_text, dict(meta)))
        return list(self.snippets)


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


@pytest.mark.asyncio
async def test_stream_reply_llm_includes_short_term_context():
    stub_llm = _StubLLMClient(["Done"])
    memory_turns = [
        MemoryTurn(role="user", content="之前的提问"),
        MemoryTurn(role="assistant", content="之前的回答"),
    ]
    memory_store = _StubMemoryStore(memory_turns)
    service = ChatService(
        settings=_make_settings(enabled=True, stm_enabled=True),
        llm_client_factory=lambda: stub_llm,
        memory_store=memory_store,
    )

    async for _ in service.stream_reply("sess-ctx", "新的问题", meta={}):
        pass

    assert memory_store.calls
    sent_messages = stub_llm.calls[0]
    assert sent_messages[0]["role"] == "user" or sent_messages[0]["role"] == "system"
    assert any(msg["content"] == "之前的提问" for msg in sent_messages)
    assert any(msg["content"] == "之前的回答" for msg in sent_messages)


@pytest.mark.asyncio
async def test_stream_reply_llm_includes_ltm_snippets():
    stub_llm = _StubLLMClient(["Done"])
    ltm_client = _StubLTMClient(["记忆片段一", "记忆片段二"])
    service = ChatService(
        settings=_make_settings(enabled=True, ltm_enabled=True, base_url="http://ltm"),
        llm_client_factory=lambda: stub_llm,
        ltm_client=ltm_client,
    )

    async for _ in service.stream_reply("sess-ltm", "当前问题", meta={"lang": "zh"}):
        pass

    assert ltm_client.calls
    sent_messages = stub_llm.calls[0]
    system_blocks = [m for m in sent_messages if m["role"] == "system"]
    assert any("Relevant memories" in m["content"] for m in system_blocks)


@pytest.mark.asyncio
async def test_stream_reply_llm_logs_context_counts(caplog):
    stub_llm = _StubLLMClient(["Done"])
    memory_turns = [MemoryTurn(role="user", content="Q1"), MemoryTurn(role="assistant", content="A1")]
    memory_store = _StubMemoryStore(memory_turns)
    ltm_client = _StubLTMClient(["记忆片段"])
    service = ChatService(
        settings=_make_settings(enabled=True, stm_enabled=True, ltm_enabled=True, base_url="http://ltm"),
        llm_client_factory=lambda: stub_llm,
        memory_store=memory_store,
        ltm_client=ltm_client,
    )

    with caplog.at_level("INFO"):
        async for _ in service.stream_reply("sess-log", "新的问题", meta={}):
            pass

    records = [record for record in caplog.records if record.msg == "chat.context.loaded"]
    assert records
    assert records[0].stm_turns == 2
    assert records[0].ltm_snippets == 1

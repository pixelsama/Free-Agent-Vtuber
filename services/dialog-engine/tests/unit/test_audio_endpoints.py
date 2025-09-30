import base64

import pytest
from fastapi.testclient import TestClient

from dialog_engine import app as dialog_app
from dialog_engine.asr.types import AsrPartial, AsrResult
from dialog_engine.audio.types import AudioBundle, AudioMetadata


@pytest.fixture
def client():
    return TestClient(dialog_app.app)


def test_chat_audio_returns_413_when_duration_exceeded(monkeypatch, client):
    async def raise_duration_error(_body):
        raise ValueError("duration limit exceeded")

    monkeypatch.setattr(dialog_app, "_prepare_audio_request", raise_duration_error)

    resp = client.post(
        "/chat/audio",
        json={"sessionId": "s", "audio": base64.b64encode(b"foo").decode("ascii")},
    )

    assert resp.status_code == 413
    assert resp.json()["detail"] == "audio payload too large"


def test_chat_audio_returns_400_when_audio_invalid(monkeypatch, client):
    async def raise_format_error(_body):
        raise ValueError("unsupported audio encoding")

    monkeypatch.setattr(dialog_app, "_prepare_audio_request", raise_format_error)

    resp = client.post(
        "/chat/audio",
        json={"sessionId": "s", "audio": base64.b64encode(b"foo").decode("ascii")},
    )

    assert resp.status_code == 400
    assert resp.json()["detail"] == "unsupported audio"


def _fake_bundle() -> AudioBundle:
    return AudioBundle(
        pcm=b"",
        metadata=AudioMetadata(sample_rate=16000, channels=1, duration_seconds=0.5, format="audio/wav"),
    )


def _fake_asr_result() -> AsrResult:
    return AsrResult(
        text="你好",
        partials=[AsrPartial(text="你好", is_final=True)],
        duration_seconds=0.5,
        provider="mock",
    )


def test_chat_audio_records_memory_and_events(monkeypatch, client):
    recorded: list[tuple[str, str]] = []
    events: list[dict] = []

    async def fake_prepare(body):  # noqa: ANN001
        return ("sess", _fake_bundle(), "zh", {})

    async def fake_transcribe(bundle, options=None):  # noqa: ANN001
        return _fake_asr_result()

    async def fake_stream_reply(*, session_id: str, user_text: str, meta: dict):
        yield "hello"

    async def fake_remember(session_id: str, *, role: str, content: str) -> None:
        recorded.append((role, content))

    def fake_emit(**kwargs):
        events.append(kwargs)

    monkeypatch.setattr(dialog_app, "_prepare_audio_request", fake_prepare)
    monkeypatch.setattr(dialog_app.asr_service, "transcribe_bundle", fake_transcribe)
    monkeypatch.setattr(dialog_app.chat_service, "stream_reply", fake_stream_reply)
    monkeypatch.setattr(dialog_app.chat_service, "remember_turn", fake_remember)
    monkeypatch.setattr(dialog_app, "_emit_async_events", fake_emit)
    monkeypatch.setattr(dialog_app, "ENABLE_ASYNC_EXT", True)

    payload = {"sessionId": "sess", "audio": base64.b64encode(b"foo").decode("ascii")}
    resp = client.post("/chat/audio", json=payload)

    assert resp.status_code == 200
    assert ("user", "你好") in recorded
    assert ("assistant", "hello") in recorded
    assert events and events[0]["transcript"] == "你好"


def test_chat_audio_stream_records_memory(monkeypatch, client):
    recorded: list[tuple[str, str]] = []
    events: list[dict] = []

    async def fake_prepare(body):  # noqa: ANN001
        return ("sess", _fake_bundle(), "zh", {})

    async def fake_transcribe(bundle, options=None):  # noqa: ANN001
        return _fake_asr_result()

    async def fake_stream_reply(*, session_id: str, user_text: str, meta: dict):
        yield "hello"

    async def fake_remember(session_id: str, *, role: str, content: str) -> None:
        recorded.append((role, content))

    def fake_emit(**kwargs):
        events.append(kwargs)

    monkeypatch.setattr(dialog_app, "_prepare_audio_request", fake_prepare)
    monkeypatch.setattr(dialog_app.asr_service, "transcribe_bundle", fake_transcribe)
    monkeypatch.setattr(dialog_app.chat_service, "stream_reply", fake_stream_reply)
    monkeypatch.setattr(dialog_app.chat_service, "remember_turn", fake_remember)
    monkeypatch.setattr(dialog_app, "_emit_async_events", fake_emit)
    monkeypatch.setattr(dialog_app, "ENABLE_ASYNC_EXT", True)

    payload = {"sessionId": "sess", "audio": base64.b64encode(b"foo").decode("ascii")}
    with client.stream("POST", "/chat/audio/stream", json=payload) as resp:
        list(resp.iter_content())

    assert ("user", "你好") in recorded
    assert ("assistant", "hello") in recorded
    assert events and events[0]["transcript"] == "你好"

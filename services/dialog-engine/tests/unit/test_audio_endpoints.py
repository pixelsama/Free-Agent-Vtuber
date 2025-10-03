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
        chunks = list(resp.iter_text())

    transcript_stream = "".join(chunks)
    sse_events = [line for line in transcript_stream.splitlines() if line.startswith("event:")]

    assert sse_events[:2] == ["event: asr-final", "event: text-delta"]
    assert sse_events[-1] == "event: done"

    assert ("user", "你好") in recorded
    assert ("assistant", "hello") in recorded
    assert events and events[0]["transcript"] == "你好"


def test_chat_vision_handles_text_and_image(monkeypatch, client):
    recorded: list[tuple[str, str]] = []
    describe_calls: list[dict] = []

    async def fake_describe_image(*, session_id: str, image_b64: str, prompt: str | None, mime_type: str, meta: dict):
        describe_calls.append(
            {
                "session_id": session_id,
                "prompt": prompt,
                "mime_type": mime_type,
                "meta": meta,
            }
        )
        return {"reply": "看到了一只小猫。", "prompt": prompt, "stats": {"chat": {"source": "llm"}}}

    async def fake_remember(session_id: str, *, role: str, content: str) -> None:
        recorded.append((role, content))

    events: list[dict] = []

    def fake_emit(**kwargs):
        events.append(kwargs)

    monkeypatch.setattr(dialog_app.chat_service, "describe_image", fake_describe_image)
    monkeypatch.setattr(dialog_app.chat_service, "remember_turn", fake_remember)
    monkeypatch.setattr(dialog_app, "_emit_async_events", fake_emit)

    payload = {
        "sessionId": "sess-vision",
        "image": base64.b64encode(b"image-bytes").decode("ascii"),
        "text": "这张图片里有什么？",
        "meta": {"lang": "zh"},
    }

    resp = client.post("/chat/vision", json=payload)

    assert resp.status_code == 200
    assert describe_calls and describe_calls[0]["prompt"] == "这张图片里有什么？"
    assert describe_calls[0]["meta"]["input_mode"] == "image"
    assert ("user", "这张图片里有什么？\n[图片输入]") in recorded
    assert ("assistant", "看到了一只小猫。") in recorded
    assert events and events[0]["transcript"].startswith("这张图片里有什么？")
    body = resp.json()
    assert body["prompt"] == "这张图片里有什么？"
    assert body["reply"] == "看到了一只小猫。"


def test_chat_vision_handles_image_only(monkeypatch, client):
    recorded: list[tuple[str, str]] = []
    describe_prompts: list[str | None] = []

    async def fake_describe_image(*, session_id: str, image_b64: str, prompt: str | None, mime_type: str, meta: dict):
        describe_prompts.append(prompt)
        return {"reply": "默认描述", "prompt": prompt or "请描述这张图片。", "stats": {}}

    async def fake_remember(session_id: str, *, role: str, content: str) -> None:
        recorded.append((role, content))

    monkeypatch.setattr(dialog_app.chat_service, "describe_image", fake_describe_image)
    monkeypatch.setattr(dialog_app.chat_service, "remember_turn", fake_remember)
    monkeypatch.setattr(dialog_app, "_emit_async_events", lambda **_: None)

    payload = {
        "sessionId": "sess-vision-empty",
        "image": base64.b64encode(b"image-bytes").decode("ascii"),
    }

    resp = client.post("/chat/vision", json=payload)

    assert resp.status_code == 200
    assert describe_prompts and describe_prompts[0] is None
    assert recorded[0] == ("user", "[图片输入]")
    assert recorded[1] == ("assistant", "默认描述")
    assert resp.json()["prompt"] == "请描述这张图片。"

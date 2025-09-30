import base64

import pytest
from fastapi.testclient import TestClient

from dialog_engine import app as dialog_app


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

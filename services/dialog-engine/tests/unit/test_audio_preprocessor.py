import asyncio

import pytest

from dialog_engine.audio.preprocessor import AudioPreprocessor
from dialog_engine.audio.types import AudioPayload


@pytest.mark.asyncio
async def test_preprocessor_fallback_allows_short_audio(monkeypatch):
    monkeypatch.setattr("dialog_engine.audio.preprocessor.np", None)
    monkeypatch.setattr("dialog_engine.audio.preprocessor.sf", None)

    preprocessor = AudioPreprocessor(max_duration_seconds=1.0)
    payload = AudioPayload(
        data=b"rawpcm",
        content_type="audio/wav",
        sample_rate=16000,
        channels=1,
        duration_seconds=0.5,
    )

    bundle = await preprocessor.normalize(payload)

    assert bundle.metadata.sample_rate == 16000
    assert bundle.metadata.channels == 1
    assert bundle.metadata.duration_seconds == pytest.approx(0.5)
    assert bundle.pcm == payload.data


@pytest.mark.asyncio
async def test_preprocessor_fallback_enforces_duration_limit(monkeypatch):
    monkeypatch.setattr("dialog_engine.audio.preprocessor.np", None)
    monkeypatch.setattr("dialog_engine.audio.preprocessor.sf", None)

    preprocessor = AudioPreprocessor(max_duration_seconds=0.5)
    payload = AudioPayload(
        data=b"rawpcm",
        content_type="audio/wav",
        sample_rate=16000,
        channels=1,
        duration_seconds=1.0,
    )

    with pytest.raises(ValueError):
        await preprocessor.normalize(payload)

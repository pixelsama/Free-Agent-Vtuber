from __future__ import annotations

from typing import Optional

from .types import AudioBundle, AudioMetadata, AudioPayload


class AudioPreprocessor:
    """Normalizes audio data prior to ASR."""

    def __init__(self, *, target_sample_rate: int = 16000, target_channels: int = 1) -> None:
        self._target_sample_rate = target_sample_rate
        self._target_channels = target_channels

    async def normalize(self, payload: AudioPayload) -> AudioBundle:
        metadata = AudioMetadata(
            sample_rate=payload.sample_rate or self._target_sample_rate,
            channels=payload.channels or self._target_channels,
            duration_seconds=payload.duration_seconds or 0.0,
            format=payload.content_type,
        )
        return AudioBundle(pcm=payload.data, metadata=metadata)

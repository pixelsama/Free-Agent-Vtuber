from __future__ import annotations

from typing import Optional

from .types import AudioBundle, AudioMetadata, AudioPayload


class AudioPreprocessor:
    """Normalizes audio data prior to ASR."""

    def __init__(self, *, target_sample_rate: int = 16000, target_channels: int = 1) -> None:
        self._target_sample_rate = target_sample_rate
        self._target_channels = target_channels

    async def normalize(self, payload: AudioPayload) -> AudioBundle:
        sample_rate = payload.sample_rate or self._target_sample_rate
        channels = payload.channels or self._target_channels
        duration = payload.duration_seconds
        if duration is None or duration <= 0.0:
            bytes_per_sample = max(1, channels) * 2  # assuming 16-bit PCM
            if sample_rate > 0 and bytes_per_sample > 0:
                duration = len(payload.data) / float(sample_rate * bytes_per_sample)
            else:
                duration = 0.0
        metadata = AudioMetadata(
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration,
            format=payload.content_type,
        )
        return AudioBundle(pcm=payload.data, metadata=metadata)

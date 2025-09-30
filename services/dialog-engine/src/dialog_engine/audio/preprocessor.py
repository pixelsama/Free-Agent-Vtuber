from __future__ import annotations

import io
from typing import Optional, Tuple

try:  # pragma: no cover - optional dependency guard
    import numpy as np
except Exception:  # pragma: no cover
    np = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    import soundfile as sf
except Exception:  # pragma: no cover
    sf = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency guard
    import resampy
except Exception:  # pragma: no cover
    resampy = None  # type: ignore[assignment]

from .types import AudioBundle, AudioMetadata, AudioPayload


class AudioPreprocessor:
    """Normalizes audio data prior to ASR."""

    def __init__(
        self,
        *,
        target_sample_rate: int = 16000,
        target_channels: int = 1,
        max_duration_seconds: Optional[float] = None,
    ) -> None:
        self._target_sample_rate = target_sample_rate
        self._target_channels = target_channels
        self._max_duration_seconds = max_duration_seconds

    async def normalize(self, payload: AudioPayload) -> AudioBundle:
        pcm, sample_rate, channels = await self._extract_pcm(payload)
        duration: float
        if np is not None and pcm is not None:
            if channels != self._target_channels:
                pcm = self._mix_down(pcm, channels)
                channels = self._target_channels
            if sample_rate != self._target_sample_rate:
                pcm, changed = self._resample(pcm, sample_rate, self._target_sample_rate)
                if changed:
                    sample_rate = self._target_sample_rate
            duration = float(len(pcm)) / float(sample_rate) if sample_rate > 0 else 0.0
            pcm_int16 = np.ascontiguousarray((pcm * 32768.0).clip(-32768, 32767).astype("<i2"))
            pcm_bytes = pcm_int16.tobytes()
        else:
            # Fallback: assume incoming PCM already matches desired format
            channels = payload.channels or self._target_channels
            sample_rate = payload.sample_rate or self._target_sample_rate
            if payload.duration_seconds and payload.duration_seconds > 0:
                duration = float(payload.duration_seconds)
            elif sample_rate > 0:
                bytes_per_sample = max(1, channels) * 2
                duration = len(payload.data) / float(sample_rate * bytes_per_sample)
            else:
                duration = 0.0
            pcm_bytes = payload.data

        if self._max_duration_seconds and duration > self._max_duration_seconds:
            raise ValueError("audio duration exceeds configured limit")

        metadata = AudioMetadata(
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration,
            format=payload.content_type,
        )
        return AudioBundle(pcm=pcm_bytes, metadata=metadata)

    async def _extract_pcm(self, payload: AudioPayload) -> Tuple["np.ndarray" | None, int, int]:
        if np is None or sf is None:
            return None, payload.sample_rate or self._target_sample_rate, payload.channels or self._target_channels
        data = payload.data
        if not data:
            return np.zeros(0, dtype=np.float32), payload.sample_rate or self._target_sample_rate, self._target_channels
        try:
            audio_array, sample_rate = sf.read(io.BytesIO(data), dtype="float32")
        except Exception as exc:  # pragma: no cover - propagates decode errors
            raise ValueError("unsupported audio encoding") from exc
        if audio_array.ndim == 1:
            audio_array = audio_array[:, None]
        channels = audio_array.shape[1]
        return audio_array, int(sample_rate), channels

    def _mix_down(self, pcm: "np.ndarray", channels: int) -> "np.ndarray":
        if channels <= 1:
            return pcm
        return np.mean(pcm, axis=1, keepdims=True, dtype=np.float32).astype(np.float32)

    def _resample(self, pcm: "np.ndarray", source_rate: int, target_rate: int) -> Tuple["np.ndarray", bool]:
        if resampy is None or source_rate == target_rate or pcm.size == 0:
            return pcm, False
        pcm_flat = pcm[:, 0]
        resampled = resampy.resample(pcm_flat, source_rate, target_rate)
        return resampled[:, None].astype(np.float32), True

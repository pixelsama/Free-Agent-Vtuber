from __future__ import annotations

import asyncio
import math
import threading
from typing import Iterable, Optional

from ..types import AsrOptions, AsrPartial, AsrResult
from .base import AsrProvider

try:  # pragma: no cover - optional dependency
    from faster_whisper import WhisperModel
except Exception:  # pragma: no cover - guard for environments without faster-whisper
    WhisperModel = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
    import numpy as np
except Exception:  # pragma: no cover - guard numpy import
    np = None  # type: ignore[assignment]


class WhisperAsrProvider(AsrProvider):
    """ASR provider backed by faster-whisper."""

    name = "whisper"

    def __init__(
        self,
        *,
        model: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
        beam_size: int = 1,
        temperature: float = 0.0,
        cache_dir: Optional[str] = None,
        default_sample_rate: int = 16000,
    ) -> None:
        if WhisperModel is None:
            raise RuntimeError("faster-whisper must be installed to use WhisperAsrProvider")
        if np is None:
            raise RuntimeError("numpy must be installed to use WhisperAsrProvider")

        self._model_name = model
        self._device = device
        self._compute_type = compute_type
        self._beam_size = max(1, beam_size)
        self._temperature = max(0.0, temperature)
        self._cache_dir = cache_dir
        self._default_sample_rate = default_sample_rate

        self._model: WhisperModel | None = None
        self._model_lock = threading.Lock()

    async def transcribe(self, *, audio: bytes, options: AsrOptions) -> AsrResult:
        language = options.lang
        sample_rate = options.sample_rate or self._default_sample_rate
        enable_timestamps = options.enable_timestamps

        segments, info = await asyncio.to_thread(
            self._run_transcribe,
            audio,
            sample_rate,
            language,
            enable_timestamps,
        )

        partials: list[AsrPartial] = []
        text_parts: list[str] = []
        for segment in segments:
            segment_text = (segment.text or "").strip()
            if not segment_text:
                continue
            text_parts.append(segment_text)
            confidence = _estimate_segment_confidence(segment)
            partials.append(AsrPartial(text=segment_text, confidence=confidence, is_final=False))

        final_text = " ".join(text_parts).strip()
        duration = getattr(info, "duration", None)

        return AsrResult(
            text=final_text,
            partials=partials,
            duration_seconds=duration,
            provider=self.name,
        )

    def _run_transcribe(
        self,
        audio: bytes,
        sample_rate: int,
        language: Optional[str],
        enable_timestamps: bool,
    ) -> tuple[Iterable[object], object]:
        model = self._ensure_model()
        audio_array = self._pcm_to_float(audio, sample_rate)

        segments, info = model.transcribe(
            audio_array,
            language=language,
            beam_size=self._beam_size,
            temperature=self._temperature,
            without_timestamps=not enable_timestamps,
            task="transcribe",
        )
        segments_list = list(segments)
        return segments_list, info

    def _ensure_model(self) -> WhisperModel:
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    self._model = WhisperModel(
                        self._model_name,
                        device=self._device,
                        compute_type=self._compute_type,
                        cache_directory=self._cache_dir,
                    )
        return self._model

    def _pcm_to_float(self, pcm_bytes: bytes, sample_rate: int) -> "np.ndarray":
        if not pcm_bytes:
            return np.zeros(0, dtype=np.float32)
        pcm_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        # Normalize 16-bit PCM to [-1, 1]
        pcm_array /= 32768.0
        return pcm_array


def _estimate_segment_confidence(segment: object) -> Optional[float]:
    """Derive a rough confidence estimate from whisper segment metadata."""

    avg_logprob = getattr(segment, "avg_logprob", None)
    no_speech_prob = getattr(segment, "no_speech_prob", None)
    if avg_logprob is None and no_speech_prob is None:
        return None

    confidence = 0.0
    if avg_logprob is not None:
        # avg_logprob typically ranges [-5, 0]; map to [0, 1]
        confidence = 1.0 - math.exp(min(0.0, avg_logprob))
    if no_speech_prob is not None:
        confidence *= 1.0 - max(0.0, min(1.0, float(no_speech_prob)))
    return max(0.0, min(1.0, confidence))

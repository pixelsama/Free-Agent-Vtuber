from __future__ import annotations

from typing import Optional

from ..audio import AudioBundle
from ..settings import AsrSettings
from .providers.base import AsrProvider
from .providers.mock import MockAsrProvider

try:
    from .providers.whisper import WhisperAsrProvider
except RuntimeError:  # pragma: no cover - optional dependency not available
    WhisperAsrProvider = None  # type: ignore[assignment]
except Exception:  # pragma: no cover - defensive guard
    WhisperAsrProvider = None  # type: ignore[assignment]
from .types import AsrOptions, AsrPartial, AsrResult


class AsrService:
    """Coordinates ASR provider usage."""

    def __init__(self, *, provider: Optional[AsrProvider] = None) -> None:
        self._provider = provider or MockAsrProvider()

    @classmethod
    def from_settings(cls, cfg: AsrSettings | None) -> "AsrService":
        provider: Optional[AsrProvider] = None
        if cfg is not None:
            provider_name = (cfg.provider or "mock").strip().lower()
            if provider_name in {"mock", "fake"}:
                provider = MockAsrProvider()
            elif provider_name in {"whisper", "faster-whisper"}:
                if WhisperAsrProvider is None:
                    raise RuntimeError("Whisper provider selected but dependencies missing")
                provider = WhisperAsrProvider(
                    model=cfg.whisper_model,
                    device=cfg.whisper_device,
                    compute_type=cfg.whisper_compute_type,
                    beam_size=cfg.whisper_beam_size,
                    cache_dir=cfg.whisper_cache_dir,
                    default_sample_rate=cfg.target_sample_rate,
                )
            else:
                raise RuntimeError(f"unsupported ASR provider: {cfg.provider}")
        return cls(provider=provider)

    async def transcribe_bundle(self, bundle: AudioBundle, *, options: Optional[AsrOptions] = None) -> AsrResult:
        opts = options or AsrOptions()
        opts.sample_rate = opts.sample_rate or bundle.metadata.sample_rate
        result = await self._provider.transcribe(audio=bundle.pcm, options=opts)
        partials = list(result.partials or [])
        if not partials or not partials[-1].is_final:
            partials.append(AsrPartial(text=result.text, is_final=True))
        return AsrResult(
            text=result.text,
            partials=partials,
            duration_seconds=result.duration_seconds,
            provider=result.provider,
        )

    @property
    def provider(self) -> AsrProvider:
        return self._provider

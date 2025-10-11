from __future__ import annotations

import logging
from typing import Optional

from ..audio import AudioBundle
from ..settings import AsrSettings
from .providers.base import AsrProvider
from .providers.mock import MockAsrProvider

logger = logging.getLogger(__name__)

try:
    from .providers.whisper import WhisperAsrProvider
except RuntimeError as e:  # pragma: no cover - optional dependency not available
    logger.warning(f"WhisperAsrProvider not available: {e}")
    WhisperAsrProvider = None  # type: ignore[assignment]
except Exception as e:  # pragma: no cover - defensive guard
    logger.error(f"Failed to import WhisperAsrProvider: {e}")
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
            logger.info(f"Initializing ASR service with provider: {provider_name}")

            if provider_name in {"mock", "fake"}:
                provider = MockAsrProvider()
                logger.info("Using MockAsrProvider")
            elif provider_name in {"whisper", "faster-whisper"}:
                if WhisperAsrProvider is None:
                    error_msg = "Whisper provider selected but dependencies missing. Install faster-whisper and numpy."
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                logger.info(f"Initializing WhisperAsrProvider with model={cfg.whisper_model}, device={cfg.whisper_device}")
                provider = WhisperAsrProvider(
                    model=cfg.whisper_model,
                    device=cfg.whisper_device,
                    compute_type=cfg.whisper_compute_type,
                    beam_size=cfg.whisper_beam_size,
                    cache_dir=cfg.whisper_cache_dir,
                    default_sample_rate=cfg.target_sample_rate,
                )
            else:
                error_msg = f"Unsupported ASR provider: {cfg.provider}. Supported providers: mock, whisper"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        else:
            logger.warning("No ASR configuration provided, using default MockAsrProvider")

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

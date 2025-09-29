from __future__ import annotations

from typing import Optional

from ..audio import AudioBundle
from .providers.base import AsrProvider
from .providers.mock import MockAsrProvider
from .types import AsrOptions, AsrPartial, AsrResult


class AsrService:
    """Coordinates ASR provider usage."""

    def __init__(self, *, provider: Optional[AsrProvider] = None) -> None:
        self._provider = provider or MockAsrProvider()

    async def transcribe_bundle(self, bundle: AudioBundle, *, options: Optional[AsrOptions] = None) -> AsrResult:
        opts = options or AsrOptions()
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

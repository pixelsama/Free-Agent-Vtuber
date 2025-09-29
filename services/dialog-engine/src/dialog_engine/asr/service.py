from __future__ import annotations

from typing import Optional

from ..audio import AudioBundle
from .providers.base import AsrProvider
from .providers.mock import MockAsrProvider
from .types import AsrOptions, AsrResult


class AsrService:
    """Coordinates ASR provider usage."""

    def __init__(self, *, provider: Optional[AsrProvider] = None) -> None:
        self._provider = provider or MockAsrProvider()

    async def transcribe_bundle(self, bundle: AudioBundle, *, options: Optional[AsrOptions] = None) -> AsrResult:
        opts = options or AsrOptions()
        return await self._provider.transcribe(audio=bundle.pcm, options=opts)

    @property
    def provider(self) -> AsrProvider:
        return self._provider

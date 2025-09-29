from __future__ import annotations

import abc
from typing import AsyncGenerator

from ..types import AsrOptions, AsrPartial, AsrResult


class AsrProvider(abc.ABC):
    """Interface for ASR providers."""

    name: str

    async def stream(self, *, audio: bytes, options: AsrOptions) -> AsyncGenerator[AsrPartial, None]:
        result = await self.transcribe(audio=audio, options=options)
        partials = list(result.partials or [])
        final_emitted = False
        for partial in partials:
            final_emitted = final_emitted or partial.is_final
            yield partial
        if not final_emitted:
            yield AsrPartial(text=result.text, is_final=True)

    @abc.abstractmethod
    async def transcribe(self, *, audio: bytes, options: AsrOptions) -> AsrResult:
        """Produce a transcription for the provided audio."""
        raise NotImplementedError

from __future__ import annotations

import abc
from typing import AsyncGenerator

from ..types import AsrOptions, AsrPartial, AsrResult


class AsrProvider(abc.ABC):
    """Interface for ASR providers."""

    name: str

    async def stream(self, *, audio: bytes, options: AsrOptions) -> AsyncGenerator[AsrPartial, None]:
        result = await self.transcribe(audio=audio, options=options)
        for partial in result.partials or []:
            yield partial
        yield AsrPartial(text=result.text)

    @abc.abstractmethod
    async def transcribe(self, *, audio: bytes, options: AsrOptions) -> AsrResult:
        """Produce a transcription for the provided audio."""
        raise NotImplementedError

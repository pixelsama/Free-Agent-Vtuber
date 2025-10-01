from __future__ import annotations

from ..types import AsrOptions, AsrPartial, AsrResult
from .base import AsrProvider


class MockAsrProvider(AsrProvider):
    name = "mock"

    async def transcribe(self, *, audio: bytes, options: AsrOptions) -> AsrResult:
        text = "mock transcription"
        return AsrResult(text=text, partials=[AsrPartial(text=text, is_final=True)])

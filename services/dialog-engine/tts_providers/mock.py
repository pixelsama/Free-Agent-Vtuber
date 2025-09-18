from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from .base import TtsProvider


class MockTtsProvider(TtsProvider):
    name = "mock"

    def __init__(self, *, chunk_delay_ms: int, chunk_count: int) -> None:
        super().__init__(voice=None)
        self._chunk_delay_ms = chunk_delay_ms
        self._chunk_count = chunk_count

    async def stream(
        self,
        *,
        session_id: str,
        text: str,
        stop_event: asyncio.Event,
    ) -> AsyncGenerator[bytes, None]:
        base = text.encode("utf-8")[:8] or b"FAKE"
        for index in range(self._chunk_count):
            if stop_event.is_set():
                return
            await asyncio.sleep(max(0.0, self._chunk_delay_ms / 1000.0))
            yield base + b"-" + str(index).encode("ascii")

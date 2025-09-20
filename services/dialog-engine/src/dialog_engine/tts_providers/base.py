from __future__ import annotations

import abc
import asyncio
from typing import AsyncGenerator, Optional


class TtsProvider(abc.ABC):
    """Abstract text-to-speech provider interface."""

    name: str

    def __init__(self, *, voice: Optional[str] = None) -> None:
        self.voice = voice

    @abc.abstractmethod
    async def stream(
        self,
        *,
        session_id: str,
        text: str,
        stop_event: asyncio.Event,
    ) -> AsyncGenerator[bytes, None]:
        """Yield PCM chunks for the given text until stop_event is set."""

    async def shutdown(self) -> None:
        """Allow provider to cleanup resources if needed."""
        return None

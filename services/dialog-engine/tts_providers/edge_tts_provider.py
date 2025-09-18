from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import AsyncGenerator, Optional

try:
    import edge_tts
except ImportError as exc:  # pragma: no cover - import guard
    raise RuntimeError("edge-tts must be installed to use EdgeTtsProvider") from exc

from .base import TtsProvider


class EdgeTtsProvider(TtsProvider):
    name = "edge-tts"

    def __init__(
        self,
        *,
        voice: str,
        rate: str = "0%",
        volume: str = "+0%",
        output_format: Optional[str] = None,
    ) -> None:
        super().__init__(voice=voice)
        self._rate = rate
        self._volume = volume
        self._output_format = output_format or "riff-24khz-16bit-mono-pcm"

    async def stream(
        self,
        *,
        session_id: str,
        text: str,
        stop_event: asyncio.Event,
    ) -> AsyncGenerator[bytes, None]:
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self._rate,
            volume=self._volume,
            output_format=self._output_format,
        )
        stream = communicate.stream()
        stop_waiter = asyncio.create_task(stop_event.wait())
        try:
            while True:
                next_chunk = asyncio.create_task(stream.__anext__())
                done, _ = await asyncio.wait(
                    {next_chunk, stop_waiter},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if stop_waiter in done:
                    next_chunk.cancel()
                    with suppress(asyncio.CancelledError):
                        await next_chunk
                    await communicate.stop()
                    break
                try:
                    chunk = next_chunk.result()
                except StopAsyncIteration:
                    break
                if chunk.get("type") == "audio":
                    data = chunk.get("data")
                    if data:
                        yield data
        finally:
            stop_waiter.cancel()
            with suppress(asyncio.CancelledError):
                await stop_waiter
            await stream.aclose()

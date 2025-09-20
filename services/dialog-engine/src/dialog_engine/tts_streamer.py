from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from typing import Optional

import websockets

from .tts_providers import MockTtsProvider, TtsProvider

try:
    from .tts_providers.edge_tts_provider import EdgeTtsProvider
except (RuntimeError, ModuleNotFoundError):
    EdgeTtsProvider = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

OUTPUT_INGEST_WS_URL = os.getenv("OUTPUT_INGEST_WS_URL", "ws://localhost:8002/ws/ingest/tts")
PROVIDER_NAME = os.getenv("SYNC_TTS_PROVIDER", "mock").strip().lower()
MOCK_CHUNK_DELAY_MS_DEFAULT = int(os.getenv("MOCK_TTS_CHUNK_DELAY_MS", "200"))
MOCK_CHUNK_COUNT_DEFAULT = int(os.getenv("MOCK_TTS_CHUNK_COUNT", "50"))
EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
EDGE_TTS_RATE = os.getenv("EDGE_TTS_RATE", "+0%")
EDGE_TTS_VOLUME = os.getenv("EDGE_TTS_VOLUME", "+0%")
EDGE_TTS_OUTPUT_FORMAT = os.getenv("EDGE_TTS_OUTPUT_FORMAT", "riff-24khz-16bit-mono-pcm")


def _build_provider(
    *,
    provider_name: str,
    chunk_count: Optional[int],
    delay_ms: Optional[int],
) -> TtsProvider:
    if provider_name == "edge-tts":
        if EdgeTtsProvider is None:
            raise RuntimeError("EdgeTTS provider requested but edge-tts dependency unavailable")
        return EdgeTtsProvider(
            voice=EDGE_TTS_VOICE,
            rate=EDGE_TTS_RATE,
            volume=EDGE_TTS_VOLUME,
            output_format=EDGE_TTS_OUTPUT_FORMAT,
        )
    # Default mock provider used for local testing and e2e scripts.
    effective_delay = int(delay_ms or MOCK_CHUNK_DELAY_MS_DEFAULT)
    effective_count = int(chunk_count or MOCK_CHUNK_COUNT_DEFAULT)
    return MockTtsProvider(chunk_delay_ms=effective_delay, chunk_count=effective_count)


async def stream_text(
    session_id: str,
    text: str,
    *,
    chunk_count: Optional[int] = None,
    delay_ms: Optional[int] = None,
) -> None:
    """Push audio chunks for the given text via the ingest websocket.

    Uses provider indicated by SYNC_TTS_PROVIDER flag (mock fallback).
    Responds to STOP control messages by cancelling provider streaming promptly.
    """

    url = os.getenv("OUTPUT_INGEST_WS_URL", OUTPUT_INGEST_WS_URL)
    provider = _build_provider(
        provider_name=PROVIDER_NAME,
        chunk_count=chunk_count,
        delay_ms=delay_ms,
    )

    stop_event = asyncio.Event()
    first_chunk_ms: Optional[float] = None

    async with websockets.connect(url) as ws:
        async def sender() -> None:
            nonlocal first_chunk_ms
            seq = 0
            start = time.perf_counter()
            try:
                async for chunk in provider.stream(
                    session_id=session_id,
                    text=text,
                    stop_event=stop_event,
                ):
                    if stop_event.is_set():
                        break
                    if first_chunk_ms is None:
                        first_chunk_ms = (time.perf_counter() - start) * 1000.0
                    payload = {
                        "type": "SPEECH_CHUNK",
                        "sessionId": session_id,
                        "seq": seq,
                        "pcm": base64.b64encode(chunk).decode("ascii"),
                        "viseme": {},
                    }
                    await ws.send(json.dumps(payload))
                    seq += 1
            finally:
                if not stop_event.is_set():
                    try:
                        await ws.send(
                            json.dumps({"type": "CONTROL", "action": "END", "sessionId": session_id})
                        )
                    except Exception:
                        pass
                await provider.shutdown()

        async def receiver() -> None:
            try:
                async for raw in ws:
                    try:
                        data = json.loads(raw) if isinstance(raw, str) else {}
                    except Exception:
                        continue
                    if data.get("type") == "CONTROL" and str(data.get("action")).upper() == "STOP":
                        stop_event.set()
                        await ws.send(
                            json.dumps({"type": "CONTROL", "action": "STOP_ACK", "sessionId": session_id})
                        )
                        break
            except Exception:
                stop_event.set()

        receiver_task = asyncio.create_task(receiver())
        try:
            await sender()
        finally:
            if not receiver_task.done():
                receiver_task.cancel()
                try:
                    await receiver_task
                except asyncio.CancelledError:
                    pass
            if not ws.closed:
                try:
                    await ws.close()
                except Exception:
                    pass
    _ = first_chunk_ms  # reserved for future metrics wiring

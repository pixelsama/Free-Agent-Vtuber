import asyncio
import base64
import os
import websockets
import json
from typing import AsyncGenerator, Optional


OUTPUT_INGEST_WS_URL = os.getenv("OUTPUT_INGEST_WS_URL", "ws://localhost:8002/ws/ingest/tts")
CHUNK_DELAY_MS_DEFAULT = int(os.getenv("MOCK_TTS_CHUNK_DELAY_MS", "200"))  # 每片默认 200ms
CHUNK_COUNT_DEFAULT = int(os.getenv("MOCK_TTS_CHUNK_COUNT", "50"))        # 默认 50 片


async def _mock_audio_chunks(text: str, *, chunk_count: int, delay_ms: int, stop_event: asyncio.Event) -> AsyncGenerator[bytes, None]:
    """Yield many small fake PCM chunks with delay; stop promptly on stop_event.

    For M2 scaffolding only. Replace with real provider in M4.
    """
    # Build a small deterministic payload per chunk (content not important for transport layer test)
    base = text.encode("utf-8")[:8] or b"FAKE"
    for i in range(chunk_count):
        if stop_event.is_set():
            return
        await asyncio.sleep(max(0.0, delay_ms / 1000.0))
        yield base + b"-" + str(i).encode("ascii")


async def stream_text(session_id: str, text: str, *, chunk_count: Optional[int] = None, delay_ms: Optional[int] = None) -> None:
    """Connect to Output Handler ingest WS and push mock speech chunks; handle STOP.

    - Produces many chunks with configurable delay (env or params) to facilitate STOP testing.
    - Listens for CONTROL {action: STOP} from Output and stops promptly.
    """
    url = os.getenv("OUTPUT_INGEST_WS_URL", OUTPUT_INGEST_WS_URL)
    chunk_count = int(chunk_count or CHUNK_COUNT_DEFAULT)
    delay_ms = int(delay_ms or CHUNK_DELAY_MS_DEFAULT)

    stop_event = asyncio.Event()

    async with websockets.connect(url) as ws:
        async def sender() -> None:
            seq = 0
            async for chunk in _mock_audio_chunks(text, chunk_count=chunk_count, delay_ms=delay_ms, stop_event=stop_event):
                if stop_event.is_set():
                    break
                msg = {
                    "type": "SPEECH_CHUNK",
                    "sessionId": session_id,
                    "seq": seq,
                    "pcm": base64.b64encode(chunk).decode("ascii"),
                    "viseme": {},
                }
                await ws.send(json.dumps(msg))
                seq += 1
            # signal end (only if not stopped)
            if not stop_event.is_set():
                await ws.send(json.dumps({"type": "CONTROL", "action": "END", "sessionId": session_id}))

        async def receiver() -> None:
            # listen for STOP from Output and set stop_event
            try:
                async for raw in ws:
                    try:
                        data = json.loads(raw) if isinstance(raw, str) else {}
                    except Exception:
                        continue
                    if data.get("type") == "CONTROL" and str(data.get("action")).upper() == "STOP":
                        stop_event.set()
                        # Acknowledge STOP
                        await ws.send(json.dumps({"type": "CONTROL", "action": "STOP_ACK", "sessionId": session_id}))
                        break
            except Exception:
                # Connection closed or other error: stop sending
                stop_event.set()

        # Run sender/receiver concurrently
        await asyncio.gather(sender(), receiver())

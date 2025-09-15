import asyncio
import base64
import os
import websockets
import json
from typing import AsyncGenerator


OUTPUT_INGEST_WS_URL = os.getenv("OUTPUT_INGEST_WS_URL", "ws://localhost:8002/ws/ingest/tts")


async def _mock_audio_chunks(text: str) -> AsyncGenerator[bytes, None]:
    """Yield a few small fake PCM chunks to simulate TTS streaming.

    For M2 scaffolding only. Replace with real provider in M4.
    """
    payloads = [b"FAKEPCM1", b"FAKEPCM2", b"FAKEPCM3"]
    for p in payloads:
        await asyncio.sleep(0.05)
        yield p


async def stream_text(session_id: str, text: str) -> None:
    """Connect to Output Handler ingest WS and push mock speech chunks.

    Dialog-engine acts as client; Output Handler relays to frontend clients.
    """
    url = os.getenv("OUTPUT_INGEST_WS_URL", OUTPUT_INGEST_WS_URL)
    async with websockets.connect(url) as ws:
        seq = 0
        async for chunk in _mock_audio_chunks(text):
            msg = {
                "type": "SPEECH_CHUNK",
                "sessionId": session_id,
                "seq": seq,
                "pcm": base64.b64encode(chunk).decode("ascii"),
                "viseme": {},
            }
            await ws.send(json.dumps(msg))
            seq += 1
        # signal end
        await ws.send(json.dumps({"type": "CONTROL", "action": "END", "sessionId": session_id}))


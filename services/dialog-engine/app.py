import asyncio
import json
import os
import time
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from .chat_service import ChatService
from .tts_streamer import stream_text as tts_stream_text


app = FastAPI()
chat_service = ChatService()
SYNC_TTS_STREAMING = os.getenv("SYNC_TTS_STREAMING", "false").lower() in {"1", "true", "yes", "on"}


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "dialog-engine", "version": "m1"}


def _sse_format(event: str, data: Dict[str, Any]) -> bytes:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\n" f"data: {payload}\n\n".encode("utf-8")


@app.post("/chat/stream")
async def chat_stream(request: Request) -> StreamingResponse:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    session_id = body.get("sessionId") or "default"
    content = body.get("content")
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=400, detail="content required")

    # Optional metadata
    meta = body.get("meta") or {}

    async def event_generator() -> AsyncGenerator[bytes, None]:
        start = time.perf_counter()
        ttft_ms: float | None = None

        async for delta in chat_service.stream_reply(session_id=session_id, user_text=content, meta=meta):
            now = time.perf_counter()
            if ttft_ms is None:
                ttft_ms = (now - start) * 1000.0
            chunk = {"content": delta, "eos": False}
            yield _sse_format("text-delta", chunk)
            # Cooperative cancellation: stop if client disconnected
            if await request.is_disconnected():
                return

        stats = {"ttft_ms": round(ttft_ms or 0.0, 1), "tokens": chat_service.last_token_count}
        yield _sse_format("done", {"stats": stats})

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@app.post("/tts/mock")
async def tts_mock(request: Request):
    """M2: Trigger a mock TTS stream to Output's ingest WS for testing.

    Body: {"sessionId": "...", "text": "..."}
    Requires SYNC_TTS_STREAMING=true.
    """
    if not SYNC_TTS_STREAMING:
        raise HTTPException(status_code=400, detail="SYNC_TTS_STREAMING disabled")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    session_id = body.get("sessionId")
    text = body.get("text")
    # Optional overrides for testing stop timing
    chunk_count = body.get("chunkCount")
    delay_ms = body.get("chunkDelayMs")
    if not session_id or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="sessionId and text required")
    await tts_stream_text(session_id=session_id, text=text, chunk_count=chunk_count, delay_ms=delay_ms)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("services.dialog-engine.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8100")), reload=False)

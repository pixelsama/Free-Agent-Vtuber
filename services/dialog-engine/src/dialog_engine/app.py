import asyncio
import base64
import binascii
import json
import logging
import os
import time
from typing import AsyncGenerator, Dict, Any, List

import redis.asyncio as redis

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .chat_service import ChatService
from .audio import AudioBundle, AudioIngestor, AudioPreprocessor, IngestLimits
from .asr import AsrOptions, AsrService
from .tts_streamer import stream_text as tts_stream_text
from .ltm_outbox import add_event as outbox_add_event, start_flush_task as outbox_start_flush


app = FastAPI()
chat_service = ChatService()
logger = logging.getLogger(__name__)
SYNC_TTS_STREAMING = os.getenv("SYNC_TTS_STREAMING", "false").lower() in {"1", "true", "yes", "on"}
ENABLE_ASYNC_EXT = os.getenv("ENABLE_ASYNC_EXT", "false").lower() in {"1", "true", "yes", "on"}
_flush_task = None

try:
    from .settings import settings as runtime_settings
except ImportError:  # pragma: no cover - defensive fallback
    runtime_settings = None

if runtime_settings is not None:
    asr_cfg = getattr(runtime_settings, "asr", None)
else:  # pragma: no cover - fallback defaults
    asr_cfg = None

_asr_enabled = bool(getattr(asr_cfg, "enabled", True))
_ingest_limits = IngestLimits(
    max_bytes=getattr(asr_cfg, "max_bytes", 5 * 1024 * 1024),
    max_duration_seconds=float(getattr(asr_cfg, "max_duration_seconds", 300.0)),
)
audio_ingestor = AudioIngestor(limits=_ingest_limits)
audio_preprocessor = AudioPreprocessor(
    target_sample_rate=int(getattr(asr_cfg, "target_sample_rate", 16000)),
    target_channels=int(getattr(asr_cfg, "target_channels", 1)),
    max_duration_seconds=float(getattr(asr_cfg, "max_duration_seconds", _ingest_limits.max_duration_seconds)),
)

try:
    asr_service = AsrService.from_settings(asr_cfg)
except Exception:  # pragma: no cover - fallback to mock provider if config invalid
    logger.exception("chat.audio.provider_init_failed")
    asr_service = AsrService()


async def _prepare_audio_request(body: Dict[str, Any]) -> tuple[str, AudioBundle, str | None, Dict[str, Any]]:
    session_id = str(body.get("sessionId") or "default")
    raw_audio = body.get("audio")
    if not isinstance(raw_audio, str) or not raw_audio.strip():
        raise HTTPException(status_code=400, detail="audio required")

    content_type = str(body.get("contentType") or "audio/wav")
    lang_value = body.get("lang")
    lang = str(lang_value).strip() if isinstance(lang_value, str) and lang_value.strip() else None
    meta_raw = body.get("meta")
    meta: Dict[str, Any]
    if isinstance(meta_raw, dict):
        meta = dict(meta_raw)
    else:
        meta = {}

    try:
        audio_bytes = base64.b64decode(raw_audio, validate=True)
    except (binascii.Error, TypeError):
        raise HTTPException(status_code=400, detail="invalid audio encoding")

    try:
        payload = await audio_ingestor.from_bytes(
            data=audio_bytes,
            content_type=content_type,
            meta={"lang": lang} if lang else None,
        )
    except ValueError:
        raise HTTPException(status_code=413, detail="audio payload too large")

    bundle = await audio_preprocessor.normalize(payload)
    return session_id, bundle, lang, meta


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "dialog-engine",
        "version": "m3-pre",
        "async_ext": ENABLE_ASYNC_EXT,
        "tts_provider": os.getenv("SYNC_TTS_PROVIDER", "mock"),
        "asr_enabled": _asr_enabled,
        "asr_provider": asr_service.provider.name if _asr_enabled else None,
    }


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
        collected: list[str] = []

        async for delta in chat_service.stream_reply(session_id=session_id, user_text=content, meta=meta):
            now = time.perf_counter()
            if ttft_ms is None:
                ttft_ms = (now - start) * 1000.0
            chunk = {"content": delta, "eos": False}
            collected.append(delta)
            yield _sse_format("text-delta", chunk)
            # Cooperative cancellation: stop if client disconnected
            if await request.is_disconnected():
                return

        stats = {"ttft_ms": round(ttft_ms or 0.0, 1), "tokens": chat_service.last_token_count}
        yield _sse_format("done", {"stats": stats})

        # Emit async events via outbox
        if ENABLE_ASYNC_EXT:
            reply_text = "".join(collected)
            correlation_id = f"{session_id}#{body.get('turn') or 0}"
            try:
                outbox_add_event(
                    "LtmWriteRequested",
                    {
                        "correlationId": correlation_id,
                        "sessionId": session_id,
                        "turn": body.get("turn"),
                        "type": "LtmWriteRequested",
                        "payload": {"text": content, "reply": reply_text, "vectorize": True},
                        "ts": int(time.time()),
                    },
                )
                outbox_add_event(
                    "AnalyticsChatStats",
                    {
                        "correlationId": correlation_id,
                        "sessionId": session_id,
                        "turn": body.get("turn"),
                        "ttft_ms": stats["ttft_ms"],
                        "tokens": stats["tokens"],
                        "ts": int(time.time()),
                    },
                )
            except Exception:
                pass

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@app.post("/chat/audio")
async def chat_audio(request: Request) -> JSONResponse:
    if not _asr_enabled:
        raise HTTPException(status_code=503, detail="audio input disabled")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    try:
        session_id, bundle, lang, meta = await _prepare_audio_request(body)
    except ValueError as exc:
        message = str(exc).lower()
        is_duration = "duration" in message
        detail = "audio payload too large" if is_duration else "unsupported audio"
        raise HTTPException(status_code=413 if is_duration else 400, detail=detail) from exc

    asr_started = time.perf_counter()
    asr_options = AsrOptions(
        lang=lang or getattr(asr_cfg, "default_lang", None),
        sample_rate=bundle.metadata.sample_rate,
    )
    try:
        asr_result = await asr_service.transcribe_bundle(bundle, options=asr_options)
    except Exception as exc:  # pragma: no cover - provider errors converted to HTTP layer
        logger.exception("chat.audio.asr_failed", extra={"sessionId": session_id})
        raise HTTPException(status_code=502, detail="asr_failed") from exc

    asr_completed = time.perf_counter()
    asr_latency_ms = (asr_completed - asr_started) * 1000.0
    transcript = (asr_result.text or "").strip()
    if not transcript:
        raise HTTPException(status_code=502, detail="empty transcript")

    meta = dict(meta)
    if lang and not meta.get("lang"):
        meta["lang"] = lang
    meta.setdefault("input_mode", "audio")
    meta.setdefault("source", "asr")

    reply_segments: list[str] = []
    try:
        async for delta in chat_service.stream_reply(session_id=session_id, user_text=transcript, meta=meta):
            reply_segments.append(delta)
    except Exception as exc:  # pragma: no cover - guard downstream failures
        logger.exception("chat.audio.reply_failed", extra={"sessionId": session_id})
        raise HTTPException(status_code=502, detail="chat_failed") from exc

    reply_completed = time.perf_counter()
    reply_text = "".join(reply_segments)

    stats = {
        "asr": {
            "provider": asr_result.provider or asr_service.provider.name,
            "latency_ms": round(asr_latency_ms, 1),
            "duration_seconds": asr_result.duration_seconds,
        },
        "chat": {
            "ttft_ms": round(chat_service.last_ttft_ms or 0.0, 1)
            if chat_service.last_ttft_ms is not None
            else None,
            "tokens": chat_service.last_token_count,
            "latency_ms": round((reply_completed - asr_completed) * 1000.0, 1),
        },
        "total_latency_ms": round((reply_completed - asr_started) * 1000.0, 1),
    }

    response_payload: Dict[str, Any] = {
        "sessionId": session_id,
        "transcript": transcript,
        "reply": reply_text,
        "stats": stats,
    }

    if asr_result.partials:
        response_payload["partials"] = [partial.text for partial in asr_result.partials]

    return JSONResponse(response_payload)


@app.post("/chat/audio/stream")
async def chat_audio_stream(request: Request) -> StreamingResponse:
    if not _asr_enabled:
        raise HTTPException(status_code=503, detail="audio input disabled")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    try:
        session_id, bundle, lang, meta = await _prepare_audio_request(body)
    except ValueError as exc:
        message = str(exc).lower()
        is_duration = "duration" in message
        detail = "audio payload too large" if is_duration else "unsupported audio"
        raise HTTPException(status_code=413 if is_duration else 400, detail=detail) from exc

    asr_started = time.perf_counter()
    asr_options = AsrOptions(
        lang=lang or getattr(asr_cfg, "default_lang", None),
        sample_rate=bundle.metadata.sample_rate,
    )
    try:
        asr_result = await asr_service.transcribe_bundle(bundle, options=asr_options)
    except Exception as exc:  # pragma: no cover - provider errors converted to HTTP layer
        logger.exception("chat.audio.asr_failed", extra={"sessionId": session_id})
        raise HTTPException(status_code=502, detail="asr_failed") from exc

    asr_completed = time.perf_counter()
    asr_latency_ms = (asr_completed - asr_started) * 1000.0
    partials = list(asr_result.partials or [])
    transcript = (partials[-1].text if partials else asr_result.text or "").strip()
    if not transcript:
        raise HTTPException(status_code=502, detail="empty transcript")

    meta = dict(meta)
    if lang and not meta.get("lang"):
        meta["lang"] = lang
    meta.setdefault("input_mode", "audio")
    meta.setdefault("source", "asr")

    async def event_generator() -> AsyncGenerator[bytes, None]:
        reply_segments: List[str] = []

        for partial in partials:
            event_name = "asr-final" if partial.is_final else "asr-partial"
            payload: Dict[str, Any] = {"text": partial.text}
            if partial.confidence is not None:
                payload["confidence"] = partial.confidence
            yield _sse_format(event_name, payload)
            if await request.is_disconnected():
                return

        reply_start = time.perf_counter()
        try:
            async for delta in chat_service.stream_reply(session_id=session_id, user_text=transcript, meta=meta):
                reply_segments.append(delta)
                chunk = {"content": delta, "eos": False}
                yield _sse_format("text-delta", chunk)
                if await request.is_disconnected():
                    return
        except Exception as exc:  # pragma: no cover - guard downstream failures
            logger.exception("chat.audio.reply_failed", extra={"sessionId": session_id})
            yield _sse_format("error", {"message": "chat_failed"})
            return

        reply_completed = time.perf_counter()
        reply_text = "".join(reply_segments)

        stats = {
            "asr": {
                "provider": asr_result.provider or asr_service.provider.name,
                "latency_ms": round(asr_latency_ms, 1),
                "duration_seconds": asr_result.duration_seconds,
            },
            "chat": {
                "ttft_ms": round(chat_service.last_ttft_ms or 0.0, 1)
                if chat_service.last_ttft_ms is not None
                else None,
                "tokens": chat_service.last_token_count,
                "latency_ms": round((reply_completed - reply_start) * 1000.0, 1),
            },
            "total_latency_ms": round((reply_completed - asr_started) * 1000.0, 1),
        }

        done_payload = {
            "sessionId": session_id,
            "transcript": transcript,
            "reply": reply_text,
            "stats": stats,
        }

        yield _sse_format("done", done_payload)

        if ENABLE_ASYNC_EXT:
            correlation_id = f"{session_id}#{body.get('turn') or 0}"
            try:
                outbox_add_event(
                    "LtmWriteRequested",
                    {
                        "correlationId": correlation_id,
                        "sessionId": session_id,
                        "turn": body.get("turn"),
                        "type": "LtmWriteRequested",
                        "payload": {"text": transcript, "reply": reply_text, "vectorize": True},
                        "ts": int(time.time()),
                    },
                )
                outbox_add_event(
                    "AnalyticsChatStats",
                    {
                        "correlationId": correlation_id,
                        "sessionId": session_id,
                        "turn": body.get("turn"),
                        "ttft_ms": stats["chat"]["ttft_ms"],
                        "tokens": stats["chat"]["tokens"],
                        "ts": int(time.time()),
                    },
                )
            except Exception:
                pass

    headers = {"Cache-Control": "no-cache", "Connection": "keep-alive"}
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)


@app.post("/tts/mock")
async def tts_mock(request: Request, background: BackgroundTasks):
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
    # 使用 FastAPI BackgroundTasks 启动后台任务，确保立即返回响应
    background.add_task(tts_stream_text, session_id=session_id, text=text, chunk_count=chunk_count, delay_ms=delay_ms)
    return {"ok": True, "sessionId": session_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dialog_engine.app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8100")), reload=False)

@app.on_event("startup")
async def _on_startup():
    global _flush_task
    if ENABLE_ASYNC_EXT:
        # best-effort Redis connection for outbox flusher
        try:
            r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", "6379")))
            await r.ping()
            _flush_task = await outbox_start_flush(r, enabled=True)
        except Exception:
            _flush_task = None

@app.on_event("shutdown")
async def _on_shutdown():
    global _flush_task
    try:
        if _flush_task:
            _flush_task.cancel()
    except Exception:
        pass

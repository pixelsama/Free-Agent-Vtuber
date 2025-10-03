# Dialog Engine Service

FastAPI service that powers synchronous chat + audio flows. It now accepts raw audio, performs ASR in-process, and emits streaming replies and analytics events.

## Endpoints

- `POST /chat/stream` – existing text SSE endpoint.
- `POST /chat/audio` – accepts base64 audio payloads, runs ASR, returns JSON transcript/reply.
- `POST /chat/audio/stream` – SSE stream that emits `asr-partial`, `asr-final`, `text-delta`, and `done` events.
- `POST /chat/vision` – accepts base64-encoded images plus optional prompts for multimodal reasoning.
- `POST /tts/mock` – helper for synchronous TTS testing (requires `SYNC_TTS_STREAMING=true`).

### Example (Sync Audio)
```bash
curl -X POST http://localhost:8100/chat/audio \
  -H "Content-Type: application/json" \
  -d '{
        "sessionId": "demo",
        "audio": "<base64 wav>",
        "lang": "zh",
        "meta": {"turn": 1}
      }'
```

### Example (Stream Audio)
Use any SSE client (curl `-N`, Postman, or VS Code REST client) to hit `/chat/audio/stream`. SSE events arrive in this order:
1. `asr-partial`/`asr-final` (with transcript text and optional confidence)
2. `text-delta` (token chunks from the reply)
3. `done` (final transcript, reply, latency statistics)

## Environment Variables

| Name | Description | Default |
| --- | --- | --- |
| `ASR_ENABLED` | Toggle audio ingestion | `true` |
| `ASR_PROVIDER` | `mock` or `whisper` | `mock` |
| `ASR_MAX_BYTES` | Max audio payload size in bytes | `5242880` |
| `ASR_MAX_DURATION_SECONDS` | Max audio duration | `300` |
| `ASR_TARGET_SAMPLE_RATE` | Preprocessor output rate | `16000` |
| `ASR_TARGET_CHANNELS` | Output channels | `1` |
| `ASR_DEFAULT_LANG` | Fallback language tag | `None` |
| `ASR_WHISPER_MODEL` | Model id for faster-whisper | `base` |
| `ASR_WHISPER_DEVICE` | `auto`, `cpu`, or `cuda` | `auto` |
| `ASR_WHISPER_COMPUTE_TYPE` | e.g. `int8`, `float16` | `int8` |
| `ASR_WHISPER_BEAM_SIZE` | Beam search width | `1` |
| `ASR_WHISPER_CACHE_DIR` | Optional model cache path | unset |
| `SYNC_TTS_STREAMING` | Enable `/tts/mock` audio push | `false` |
| `ENABLE_ASYNC_EXT` | Enables outbox + analytics events | `false` |
| `VISION_MAX_BYTES` | Max accepted image payload size in bytes | `4194304` |
| `OUTPUT_INGEST_WS_URL` | Output handler WS endpoint | `ws://localhost:8002/ws/ingest/tts` |

## Dependencies

Install from `requirements.txt`:
```bash
pip install -r services/dialog-engine/requirements.txt
```
Includes `faster-whisper`, `numpy`, `soundfile`, `resampy` for audio preprocessing.

## Testing

```bash
cd services/dialog-engine
pytest tests/unit
```

Current unit coverage includes audio ingestion, ASR service wiring, memory/outbox behavior, and endpoint validation. Integration tests can be added once Redis and downstream services are available.

## Migration Notes

- Legacy microservices (`asr-python`, `chat-ai-python`, `tts-python`) are deprecated for audio input. `dialog-engine` owns ASR + chat orchestration.
- Short-term memory database now records audio-derived turns (`remember_turn`). Ensure `STM_DB_PATH` persists across restarts if chat history is required.
- Analytics outbox emits `AnalyticsAsrStats` alongside existing chat events; configure Redis streams consumers accordingly.

## Tooling

- Docker: `docker compose up -d` (see project root) to launch full stack.
- Local dev: `uvicorn dialog_engine.app:app --reload --port 8100` (requires env vars).
- Postman/VS Code REST: import the above examples and adjust `audio` payload as needed (WAV base64).


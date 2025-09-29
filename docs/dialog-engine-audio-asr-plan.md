# Dialog Engine Audio Input & ASR Integration Plan

## 1. Background
- `dialog-engine` currently streams LLM text replies and synchronous TTS output but only accepts text input.
- Legacy standalone services (`asr-python`, `chat-ai-python`, `tts-python`) are being retired; the new flow must live entirely in `dialog-engine`.
- Goal: allow clients to send raw audio, perform automatic speech recognition (ASR) inside `dialog-engine`, and feed recognized text into the existing conversation pipeline.

## 2. Objectives
1. Accept audio input (file upload and low-latency stream) alongside existing text API.
2. Run ASR in-process with configurable providers (local Whisper/FunASR, cloud API, mock for tests).
3. Convert ASR output into conversation turns, preserving memory interactions and downstream TTS hooks.
4. Provide clear telemetry, error handling, and configuration knobs for production readiness.

## 3. Scope
- `dialog-engine` service only: new modules, endpoints, and docs.
- Audio formats: 16 kHz mono PCM WAV (primary), with automatic resampling for common alternatives (48 kHz, stereo).
- ASR providers: built-in `whisper` (local GPU/CPU), `mock` provider, pluggable interface for future services.
- Out of scope: maintaining compatibility with removed microservices, front-end recording UI implementation, or cross-service redis messaging.

## 4. High-Level Architecture
```
Client -> /chat/audio (REST or WS) -> Audio Ingestor -> Preprocessor -> ASR Pipeline -┐
                                                                            └> ChatService.stream_reply -> SSE/WebSocket reply
```

### Components
1. **Audio Ingestor** (`audio_ingest.py`)
   - Validates request, enforces size/duration limits, and stores audio temporarily (memory or `/tmp`).
   - Supports both multipart upload (`audio` file) and base64 JSON payloads.
   - For streaming, wraps FastAPI WebSocket endpoint forwarding PCM chunks into an asyncio queue.

2. **Audio Preprocessor** (`audio_preprocessor.py`)
   - Normalizes sample rate/channels via `soundfile` + `resampy`/`librosa` or `ffmpeg-python` (configurable).
   - Generates uniform NumPy float32 PCM ready for ASR providers.
   - Provides metadata (duration, energy) for logging and guardrails.

3. **ASR Service** (`asr_service.py`)
   - Defines `class AsrProvider(Protocol)` with `async def transcribe(audio: AudioBatch, options: AsrOptions) -> AsrResult`.
   - Implements providers:
     - `MockAsrProvider`: deterministic text for tests.
     - `WhisperAsrProvider`: wraps `openai-whisper` or `faster-whisper` local model with batching/timeout.
   - Handles streaming mode by yielding `AsrPartial` deltas before final transcript.

4. **Conversation Bridge**
   - Extends `chat_service.ChatService` entrypoint to accept `AudioInput` struct.
   - Writes ASR transcript into `ShortTermMemoryStore` and optional LTM outbox events before generating reply.

5. **Response Streamer**
   - Merges ASR partials and LLM deltas in single SSE/WebSocket stream for client consumption.
   - Event types: `asr-partial`, `asr-final`, `text-delta`, `done` (with stats: TTFT, ASR latency, tokens).

## 5. API Surface

### REST: `POST /chat/audio`
- Body (multipart or JSON):
  ```json
  {
    "sessionId": "uuid",
    "audioFormat": "wav",
    "sampleRate": 48000,
    "lang": "auto|zh|en",
    "audio": "<base64>"   // if JSON payload
  }
  ```
- Response: immediate acknowledgement with job stats or final result when `mode=sync` (default).
- Query params:
  - `stream=false/true`: switch to SSE streaming endpoint.
  - `mode=sync|async`: async returns task id for later retrieval (future extension).

### SSE: `POST /chat/audio/stream`
- Returns server-sent events combining ASR + LLM.
- Breaker thresholds: client disconnect aborts ASR to save resources.

### WebSocket: `/ws/chat/audio`
- Bidirectional real-time path for low-latency voice conversations.
- Protocol messages:
  - `AUDIO_START`, `AUDIO_CHUNK`, `AUDIO_END` from client.
  - `ASR_PARTIAL`, `ASR_FINAL`, `LLM_DELTA`, `TTS_READY` from server.

## 6. Configuration
- Extend `settings.py` with `AsrSettings`:
  ```python
  class AsrSettings(BaseModel):
      enabled: bool = True
      provider: str = Field(default="whisper", regex="^(mock|whisper|custom:.+)$")
      max_duration_sec: int = 300
      max_size_mb: int = 25
      sample_rate: int = 16000
      stream_buffer_ms: int = 500
      device: str = "auto"  # cpu/cuda
      whisper_model: str = "small"
      language: str | None = None
  ```
- Allow env overrides (e.g., `ASR_PROVIDER`, `ASR_WHISPER_MODEL`, `ASR_MAX_DURATION_SEC`).
- Add logging flags and metrics prefix `dialog_engine.asr.*`.

## 7. Telemetry & Error Handling
- Structured logs on start/end: include sessionId, audio duration, provider, latency, success flag.
- Prometheus-compatible counters:
  - `asr_requests_total`, `asr_failures_total`, `asr_latency_seconds`, `asr_partial_updates_total`.
- Expose `/metrics` (if not already) or reuse existing instrumentation pipeline.
- Graceful fallbacks: on ASR failure, return HTTP 502 with error code `ASR_FAILED`; allow clients to retry or fall back to text input.

## 8. Implementation Steps
1. **Scaffold modules**
   - Create `dialog_engine/audio/` package with ingest, preprocessing, types.
   - Create `dialog_engine/asr/` package with provider interfaces and mock implementation.
2. **Synchronous path**
   - Implement `/chat/audio` endpoint: request parsing, audio validation, call `AsrService.transcribe`, forward transcript to `ChatService.stream_reply`.
   - Ensure response includes ASR + LLM stats.
3. **Streaming path (SSE)**
   - Add generator combining ASR partials (async queue) and LLM reply; share cancellation with client disconnect detection (reuse `request.is_disconnected()`).
4. **Provider integrations**
   - Ship `MockAsrProvider` default.
   - Integrate local Whisper via `faster-whisper` (CPU) with caching; guard optional dependency import.
5. **Resource management**
   - Enforce max duration/size; reject large files early with `413 Payload Too Large`.
   - Use temp files with automatic cleanup or in-memory BytesIO (for <5 MB).
6. **Memory + Analytics**
   - Record ASR transcript as `user` turn in short-term memory before LLM call.
   - Extend outbox events: `AnalyticsAsrStats`, `LtmWriteRequested` with speech metadata if async ext enabled.
7. **Testing**
   - Unit tests for ingest, preprocessing, ASR mock, endpoint validation (`pytest` + FastAPI `AsyncClient`).
   - Integration test using fixture audio -> ensures final SSE stream contains `asr-final` before `done`.
   - Load test script (optional) to evaluate concurrency and CPU usage.
8. **Documentation & Ops**
   - Update README (`services/dialog-engine/README.md`) with new env vars, usage.
   - Add Postman/VSCode REST examples.
   - Provide migration notes explaining deprecation of old ASR/chat/tts services.

## 9. Milestones
1. **MVP (Week 1)**: `/chat/audio` sync endpoint with mock ASR provider, plumbing to chat pipeline, minimal tests.
2. **Whisper Integration (Week 2)**: local model support, resource limits, SSE streaming with partials.
3. **Real-Time WS (Week 3)**: WebSocket ingestion, partial-asr coalescing, concurrency hardening.
4. **Production Hardening (Week 4)**: metrics, alerting, documentation, load test, feature flag rollout.

## 10. Risks & Mitigations
- **Model Download Size**: Whisper models large; allow configurable cache dir and document warm-up.
- **Latency on CPU**: Provide `device` and `model` tunables; support GPU if available.
- **Security**: Validate audio MIME/types, limit upload size, sanitize temp paths.
- **Cancellation**: Ensure streaming cancellation propagates to ASR task to avoid leaked workers.

## 11. Open Questions
- Do we need diarization or word-level timestamps in MVP? (currently no, but interface leaves room in `AsrResult`.)
- Should ASR operate in background tasks or run inline per request? (MVP inline, revisit when concurrency requirements known.)
- Any compliance requirements for storing voice data? (Assume no persistent storage beyond temp files.)


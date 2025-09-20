# Sync-Core Status & Next Steps (M3/M4)

_Last updated: 2025-09-18_

## 1. Summary
- **M3 (Outbox + Redis Streams)** is functionally complete and verified.
- **M4 (real-time TTS + STOP)** core path is working with EdgeTTS; further soak tests and observability are still pending.
- Async workers (`services/async-workers/`) are in place as the new home for long-term memory / analytics events but still contain placeholder logic.

## 2. Current State
### Dialog Engine
- Source relocated to `services/dialog-engine/src/dialog_engine/` with pluggable TTS providers (`mock`, `edge-tts`).
- EdgeTTS streaming validated manually via `/tts/mock` + output-handler ingest.
- `ENABLE_ASYNC_EXT=true` now pushes events to SQLite outbox → Redis Streams.
- Health endpoint exposes active provider; compose/dev env exports all relevant env vars (`SYNC_TTS_STREAMING`, `SYNC_TTS_PROVIDER`, Edge voice/rate/volume, etc.).

### Output Handler
- Internal ingest WS (`/ws/ingest/tts`) functional. Requires `SYNC_TTS_STREAMING=true`, `SYNC_TTS_BARGE_IN=true`.
- `/internal/output/health` confirms ingest connectivity (`ingest_connected`).

### Async Workers (M3)
- Containers defined in `docker-compose.dev.yml` (`async-workers-ltm`, `async-workers-analytics`).
- Currently only log consumed messages; need to integrate real LTM/analytics code paths.

## 3. Outstanding Issues / TODOs
1. **EdgeTTS soak test**
   - Run 30–60 min loop (`scripts/e2e_stop_latency.py` in repeated rounds) to validate stability.
   - Collect STOP_ACK / last_chunk latency metrics (p50/p95/p99) and watch for reconnect errors.
2. **Metrics & Observability**
   - Expose TTFT (first audio chunk) and STOP latency as structured logs or Outbox events.
   - Add counters for ingest connect/disconnect, error retries.
3. **LLM Integration (M4 scope)**
   - Replace `chat_service.stream_reply()` mock with real LLM streaming (OpenAI/Claude, etc.).
   - Ensure correlation IDs/tokens recorded for analytics.
4. **Async workers real implementation**
   - Migrate long-term-memory write/search logic into `ltm_worker.py` (or shared library) consuming `events.ltm`.
   - Extend `analytics_worker.py` to persist metrics (DB or external telemetry).
5. **Testing coverage**
   - Add unit/functional tests for `edge_tts_provider` with mocked `Communicate` (already partially done) + STOP cancel flows.
   - Add integration test that flips `ENABLE_ASYNC_EXT=true` and asserts stream consumption.
6. **Documentation / Onboarding**
   - Update README and service-specific docs to reference new package layout, env vars, and async worker setup.
7. **Deployment**
   - Confirm production compose/k8s manifests mounted paths reflect `/app/src` layout.
   - Consider building slim runtime images without host bind mounts for production.

## 4. Verification Checklist
- [ ] `docker compose -f docker-compose.dev.yml up -d dialog-engine output-handler async-workers-*`
- [ ] `curl http://localhost:8000/internal/output/health` → `ingest_connected: true`
- [ ] `python scripts/e2e_stop_latency.py --runs 3` (quick check) → low STOP latency
- [ ] Redis Streams populated (`redis-cli XLEN events.ltm`) and async workers log events
- [ ] SQLite outbox drained (`SELECT COUNT(*) FROM outbox_events WHERE delivered=0` → 0)

## 5. Useful Commands
```bash
# Start services (dialog-engine + workers) in dev mode
ENABLE_ASYNC_EXT=true SYNC_TTS_STREAMING=true SYNC_TTS_BARGE_IN=true \ 
SYNC_TTS_PROVIDER=edge-tts docker compose -f docker-compose.dev.yml up -d \
  dialog-engine output-handler async-workers-ltm async-workers-analytics

# Watch worker logs
docker compose -f docker-compose.dev.yml logs -f async-workers-ltm async-workers-analytics

# Soak runner (example)
python scripts/e2e_stop_latency.py --runs 10 --chunk-delay-ms 200 --chunk-count 150
```

## 6. References
- ADR-0001-sync-core.md (updated with new directory layout)
- ADR-0002-redis-keyspace-plan.md (notes Outbox → Streams mapping)
- `docs/新重构计划.md` for milestone breakdown

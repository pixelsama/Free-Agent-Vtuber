# Dialog Engine — Real LLM Enablement Plan

## 1. Goals
- Replace the hard-coded reply generator in `dialog-engine` with a production-ready LLM-backed pipeline.
- Preserve streaming behaviour (`/chat/stream` SSE) with fast time-to-first-token (TTFT) and backpressure-aware cancellation.
- Integrate short-term memory and optional LTM retrieval into the prompt while keeping latency budget under 600 ms TTFT.
- Maintain feature flag guardrails so the simulated flow can remain as fallback during rollout.

## 2. Current State Snapshot
- `ChatService.stream_reply` generates static text using `_craft_reply`; no external API calls or memory injection.
- `dialog-engine` exposes `/chat/stream` for Input Handler; SSE stream emits `text-delta` and `done` events only.
- Outbox events (`LtmWriteRequested`, `AnalyticsChatStats`) depend on collected text already baked in `chat_service`.
- `chat-ai-python` already wraps OpenAI via `AsyncOpenAI` with system prompt, Redis context, and LTM snippets but lives outside the new synchronous flow.
- Secrets (`OPENAI_API_KEY`, etc.) are managed per existing guidelines through `.env`/Docker.

## 3. Target End-To-End Flow
1. Input Handler issues `POST /chat/stream` with session payload.
2. `ChatService` (new) orchestrates:
   - Fetch short-term memory turns (SQLite) and optional Redis context.
   - Perform LTM retrieval (hits `memory-python` or a forthcoming vector store) when `ENABLE_LTM_INLINE=true`.
   - Call shared LLM client (`chat-ai` extraction or direct OpenAI) using streaming API.
   - Emit word/token deltas to SSE stream as they arrive.
3. On completion, flush metrics and emit outbox events like today.
4. Downstream (Output Handler / TTS) remains unchanged; only text source differs.

## 4. Design Decisions
- **LLM Client Location**: Export reusable client from `chat-ai-python` (e.g., move to `utils/llm_client`) or embed minimal client within `dialog-engine`. Decision to be made during implementation; document pros/cons.
- **Streaming Interface**: Use OpenAI-compatible SSE (via `AsyncOpenAI.chat.completions.create(..., stream=True)`), adapt to generator that yields pre-tokenized strings.
- **Prompt Framework**: Compose messages from (system prompt, memory context, LTM snippets, user text); keep deterministic ordering to help caching/testing.
- **Cancellation**: On client disconnect or stop signal, abort OpenAI stream via `aclose()` and skip residual events.
- **Feature Flags**:
  - `ENABLE_REAL_LLM=true` toggles new flow.
  - Fallback path retains current mock generator when disabled.

## 5. Implementation Tasks
### Phase 1 — Foundations
- Extract/share LLM config (model, temperature, timeout) into `dialog-engine` settings.
- Add environment variables with sensible defaults to `.env.example` and Dockerfiles.
- Write wrapper for OpenAI streaming with structured logging and retries (respect network sandbox constraint in prod).

### Phase 2 — Chat Service Upgrade
- Refactor `ChatService` to accept dependencies (`LLMClient`, `MemoryStore`, `MetricsSink`).
- Implement `stream_reply` to consume streaming responses, handle role conversions, and produce SSE-ready deltas.
- Add instrumentation: TTFT, token counts, error types.
- Gate old implementation with flag for quick rollback.

### Phase 3 — Context and Memory
- Wire in short-term memory reads (existing SQLite or new repository module).
- Integrate optional LTM retrieval by HTTP/RPC call to `memory-python` (mock or actual vector store).
- Merge retrieved context into prompt with guardrails (token budgeting, dedupe).

### Phase 4 — Testing & Observability
- Unit tests mocking `LLMClient.stream()` for success, timeout, cancellation.
- Integration test hitting `/chat/stream` with `ENABLE_REAL_LLM=false/true` to verify fallback.
- Add logging hooks (structured JSON) for prompt size, streaming duration, and retry attempts.
- Update Prometheus or log-based dashboards if available.

### Phase 5 — Rollout
- Deploy behind flag in staging; validate TTFT, completeness, cancellation, analytics events.
- Gradually enable in production sessions while monitoring error rates.
- Keep mock fallback accessible for low-bandwidth/offline demos.

## 6. Dependencies & Coordination
- Align with `chat-ai-python` maintainers if extracting shared clients.
- Ensure `memory-python` exposes retrieval endpoint with latency < 150 ms.
- Confirm with DevOps on OpenAI key provisioning and rate limit monitoring.
- Coordinate with frontend for any user-facing copy changes once responses become richer.

## 7. Risk & Mitigation
- **LLM latency spikes** → add timeout + fallback to mock reply, monitor via analytics stream.
- **Token budget overflow** → enforce truncation of memory and user text to maintain prompt < 4k tokens.
- **Error handling gaps** → implement retry/backoff for transient network errors, map known OpenAI errors to user-friendly fallbacks.
- **Cost escalation** → add per-session usage metrics; optionally support cheaper model for casual sessions.

## 8. Acceptance Criteria
- With `ENABLE_REAL_LLM=true`, `/chat/stream` serves LLM-generated text with TTFT < 1.5 s in 95th percentile during staging load.
- Analytics outbox events report real token counts as returned by the provider.
- Fallback path (`ENABLE_REAL_LLM=false`) behaves exactly as current mock implementation.
- Automated tests cover streaming success, cancellation, and fallback toggling.
- Rollout plan executed with documented checkpoints and monitoring dashboards linked in runbook.

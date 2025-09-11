# Long-Term Memory Integration Plan

## Goal
Integrate `services/long-term-memory-python` (LTM) into the existing Redis-based pipeline to store/retrieve semantically relevant memories that enrich AI replies, while remaining backward compatible.

## Current Gaps
- LTM is only defined in `docker-compose.yml` and not referenced by other services.
- No use of `ltm_requests`/`ltm_responses` channels; `memory-python` only listens to `user_input_queue` and `ai_responses`.

## Design Overview
- Publish-on-write: When `memory-python` stores a user/AI message, also publish a light-weight `memory_updates` event for LTM to index via Mem0/pgvector.
- Request/response for retrieval and profiles:
  - Requests: push JSON to Redis list `ltm_requests` (BLPOP by LTM worker).
  - Responses: publish JSON to channel `ltm_responses` with `request_id` for correlation.
- Consumers:
  - LTM subscribes to `memory_updates` (pub/sub) for continuous ingest.
  - LTM consumes `ltm_requests` for on-demand `search|add|profile_get|profile_update`.

## Message Contracts (Redis)
- Channel `memory_updates` (pub/sub):
  - `{ "user_id": "u1", "content": "text", "source": "user|ai", "timestamp": 1712345678, "meta": {"session_id":"s1"} }`
- Queue `ltm_requests` (list):
  - `{ "request_id": "req-uuid", "type": "search|add|profile_get|profile_update", "user_id": "u1", "data": { ... } }`
- Channel `ltm_responses` (pub/sub):
  - `{ "request_id": "req-uuid", "user_id": "u1", "success": true, "memories": [ ... ], "user_profile": { ... }, "error": null }`
(Models already exist under `services/long-term-memory-python/src/models/messages.py`).

## Service Changes
- memory-python
  - On storing user/AI messages, `publish('memory_updates', MemoryUpdateMessage)`.
  - Optional: feature flag `ENABLE_LTM_PUBLISH=true`.
- chat-ai-python
  - Before generating a reply, send `LTMRequest(type='search', data={ query: <last_user_text>, limit: 5 })` to `ltm_requests` and wait for `ltm_responses` with matching `request_id` (timeout 300–800ms). Merge top-k memories into prompt/context.
  - On timeout or error, proceed without LTM.
- long-term-memory-python
  - Implement two loops in `main.py`:
    - Pub/Sub subscriber for `memory_updates` → `MessageProcessor.process_memory_update`.
    - BLPOP loop on `ltm_requests` → route by `type` → publish `LTMResponse` to `ltm_responses`.

## Configuration
- Env vars (all services as needed):
  - `LTM_REQUESTS_QUEUE=ltm_requests`, `LTM_RESPONSES_CHANNEL=ltm_responses`, `MEMORY_UPDATES_CHANNEL=memory_updates`.
  - `ENABLE_LTM=true|false` for requester services (e.g., chat-ai, gateway).
- docker-compose
  - Ensure `chat-ai` and `memory` depend on `redis` (already) and optionally add `long-term-memory` for visibility; no strict dependency required.

## Example Snippets
- Publish memory update (memory-python):
  - `await redis_client.publish("memory_updates", json.dumps({...}))`
- Send LTM search (chat-ai-python):
  - `await redis.lpush("ltm_requests", json.dumps({"request_id": rid, "type":"search", "user_id": uid, "data": {"query": q, "limit": 5}}))`
  - Subscribe `ltm_responses` and filter by `request_id` (with timeout).

## Testing & Rollout
- Unit tests: validate publish from memory service; requester waits/correlates responses; LTM handlers route by `type` and publish responses.
- Integration test (docker-compose.dev): bring up `redis`, `chat-ai`, `memory`, `long-term-memory`; simulate a user message, assert search request emitted and response consumed.
- Rollout: behind `ENABLE_LTM`; enable publish first, then enable retrieval in chat-ai once indexing is healthy.


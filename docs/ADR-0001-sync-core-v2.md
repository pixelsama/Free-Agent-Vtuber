# Free-Agent-Vtuber 同步主链路重构实施计划（v2）

本计划基于现有仓库与服务形态（FastAPI/WS + Redis + TTS/ASR/Memory/Chat-AI 微服务），在不破坏可运行性的前提下，分阶段推进“同步、流式、可打断”的主链路（dialog-engine），并将长期记忆与观测放入异步扩展层（Redis Streams + Outbox）。

目标优先级：稳定性 > 首包延迟 > 打断控制 > 全量流式化 > 异步扩展可靠性。

---

## 1. 现状概要（基于仓库）

- Input Handler（services/input-handler-python）通过 WebSocket 接收文本/音频，落临时文件，推入 Redis 列表：`user_input_queue`（文本）、`asr_tasks`（音频）。并桥接 `asr_results`→`user_input_queue`。
- Memory（services/memory-python）消费 `user_input_queue`，存入 Redis（全局/用户上下文），发布 `memory_updates`。监听 `ai_responses` 存 AI 回复。
- Chat-AI（services/chat-ai-python）监听 `memory_updates`，调用 OpenAI 或规则回复，发布 `ai_responses`，并可请求 LTM（使用 `ltm_requests`/`ltm_responses`）。
- TTS（services/tts-python）消费 TTS 请求列表，生成整段音频文件，发布到 `task_response:{task_id}`（Output 再分块推给前端）。
- Output Handler（services/output-handler-python）作为 WS 服务端，订阅 `task_response:{task_id}`，将文本+音频文件分块回推给前端。
- Gateway（services/gateway-python）仅代理 WS，未代理 HTTP SSE。

问题：主链路高度异步，端到端首音延迟较大，打断难以生效；TTS/Output 以“落地文件再推送”为主，不具备真流式与STOP回控。

---

## 2. 目标与范围

- 引入 dialog-engine 作为“同步主链路”入口：Input → dialog-engine（HTTP SSE），dialog-engine → Output（本地 WS），支持文本流与（逐步）音频分片推送与打断。
- 保留现有微服务与路径作为回退（Redis 列表/频道仍可用）。
- 将长期记忆与观测改为 Redis Streams（采用 Outbox 提升可靠性），逐步替换现有 Pub/Sub/列表用法。

不在本次：前端重大改造、复杂插件生态、视觉/3D 模块重写。

---

## 3. 分阶段实施（建议节奏）

### M1：同步文本流（SSE）打通，维持非流式 TTS 回传

- 新增服务 `services/dialog-engine`：
  - `POST /chat/stream`（SSE）：接收 `{sessionId, turn, type, content, meta}`，按 token/delta 流式推送 `text-delta` 与 `done`。
  - 上下文：初期可直接从 Redis 读取 global/user context，后续迁到 SQLite（WAL）。
  - LLM：内置简单流式生成（OpenAI/规则降级），先不改 Chat-AI 服务，减少耦合。
- Input Handler：新增 Flag 分支，文本优先走 `POST /chat/stream`，失败回退旧队列。
- Output Handler：不改；仍通过 `task_response:{task_id}` 和文件分块向前端播音频（音频与文本的展示暂不同步）。
- 验收：文本首包（TTFT）P95 < 250ms（本地），链路稳定。

### M2：半流式 TTS 与打断信令

- Output Handler 新增“内部 WS”端点（仅内网）：`/ws/ingest/tts`，用于接收 dialog-engine 推送的音频小分片与控制事件，并中继给前端连接：
  - 入站消息：
    - `{"type":"SPEECH_CHUNK","sessionId","seq","pcm":"<base64>","viseme":{...}}`
    - `{"type":"CONTROL","action":"END"|"STOP_ACK"}`
  - 回控消息（由 Output 回给 dialog-engine）：
    - `{"type":"CONTROL","action":"STOP","sessionId"}`
- dialog-engine 增加简易 TTS 分片推送能力（可先按“句边界/固定切片”模拟），并支持收到 STOP 立即清空队列、终止后续分片。
- 验收：
  - 音频首包 P95 < 800ms；
  - 发出 STOP 后 <100ms 停止继续推送（以测试桩模拟验证）。

### M3：短期记忆本地化 + Outbox/Redis Streams 引入

- dialog-engine：
  - 使用 SQLite（WAL）存最近 N 轮 `turns(sessionId, turn, role, text, ts)`；
  - 添加 `outbox_events(id, type, payload, created_at, delivered)`；后台 worker 批量 XADD 至：
    - `events.ltm`（长期记忆写入/embedding/摘要）
    - `events.analytics`（观测与指标）
- 新增 `services/async-workers`：`ltm_worker.py`、`analytics_worker.py` 消费对应 Streams（消费者组）。
- LTM 服务：逐步从 `memory_updates`/`ltm_requests` 迁移为消费 `events.ltm`（过渡期可保留桥接层）。
- 验收：Outbox → Streams 全链路可观测（未投递重试、投递成功打 delivered）。

### M4：TTS 真流与细粒度打断

- 重构 TTS provider 调用：
  - EdgeTTS：利用其 `stream()` 边合成边产出；
  - OpenAI：按 API 能力做分片；
  - 将 provider 运行置于 dialog-engine 内部 task，分片即产即发；打断通过取消任务/关闭底层流实现“句内打断”。
- Output Handler 对外协议不改（前端仍收 WS 分片），仅优化内部管线。
- 验收：长文本连续播放稳定，句内打断成功率高，端到端无明显卡顿。

---

## 4. 接口契约（v2）

### 4.1 Input → dialog-engine（SSE）

- Endpoint：`POST /chat/stream`
- 请求（JSON）：
```json
{
  "sessionId": "live-001",
  "turn": 42,
  "type": "TEXT|ASR_FINAL|COMMAND",
  "content": "今晚玩什么？",
  "meta": {"lang": "zh", "emotionHint": null}
}
```
- SSE 事件：
  - `text-delta`: `{"content":"……分片文本……","eos":false}`
  - `done`: `{"stats":{"ttft_ms":130, "tokens":57}}`

说明：M1 仅文本；M2 起可增加 `control` 事件提示 Output 准备开播 TTS。

### 4.2 dialog-engine → Output（内部 WS，双向）

- 路径：`/ws/ingest/tts`
- 出站（dialog-engine → Output）：
```json
{"type":"SPEECH_CHUNK","sessionId":"live-001","seq":17,"pcm":"<base64>","viseme":{"AA":0.7,"M":0.1},"ts":1736900000}
{"type":"CONTROL","action":"END","sessionId":"live-001"}
```
- 回控（Output → dialog-engine）：
```json
{"type":"CONTROL","action":"STOP","sessionId":"live-001"}
```

说明：对外（前端）协议维持现状，或同步收敛到同一事件格式，减少双份实现。

### 4.3 异步扩展（M3+）

- Streams：`events.ltm`、`events.analytics`（可扩展 `events.plugins`）。
- Outbox 事件载荷示例：
```json
{
  "correlationId": "live-001#42",
  "sessionId": "live-001",
  "turn": 42,
  "type": "LtmWriteRequested",
  "payload": {"text": "今晚玩什么？", "reply": "今晚我们尝试……", "vectorize": true},
  "ts": 1736900000
}
```

---

## 5. Feature Flags 与配置

- `ENABLE_SYNC_CORE=true`：Input 优先走 `/chat/stream`（失败回退旧队列）。
- `SYNC_TTS_STREAMING=false`（M2 起可开）：开启音频分片推送。
- `SYNC_TTS_BARGE_IN=false`（M2 起可开）：允许 STOP 打断。
- `ENABLE_STREAMS_OUTBOX=false`（M3 起可开）：启用 Outbox + Streams。
- `ENABLE_LTM=false`：按需检索 LTM（与 Chat-AI 当前逻辑保持一致或改接 Streams）。

默认保守：逐项开启、逐项验证。

---

## 6. 服务改动清单（按阶段）

### dialog-engine（新增，M1）

- `app.py`：FastAPI + SSE 端点；健康检查。
- `chat_service.py`：上下文拼接（先读 Redis），流式 LLM（OpenAI/规则降级）。
- `tts_streamer.py`（M2+）：音频分片与队列、STOP 处理；与 Output 的内部 WS 客户端。
- `memory_shortterm.py`（M3）：SQLite(WAL) turns 表；最近 N 轮裁剪。
- `ltm_outbox.py`（M3）：Outbox 写入与投递。

### input-handler-python（M1）

- 新增配置与 Flag；在收到文本时尝试调用 `/chat/stream`（SSE），将 `text-delta` 直接转发给前端或记录为提示（当前前端链路主要经 Output，文本展示策略可先保持原样）。失败回退 `user_input_queue`。

### output-handler-python（M2）

- 新增内部 WS 端点 `/ws/ingest/tts`：
  - 接受 dialog-engine 音频分片与控制事件；
  - 将分片中继给前端连接（沿用现有分块传输格式或统一为 SPEECH_CHUNK 事件）；
  - 接收前端/运维 STOP 指令并回传给 dialog-engine。

### tts-python（过渡期保持，M4 再重构）

- M1-M2：保留“整段生成+文件落地”供旧链路回退与兼容。
- M4：provider 真流化逻辑迁入 dialog-engine，或将 tts 服务改为“流式 gRPC/WS 提供者”。

### memory-python / long-term-memory-python（M3）

- 逐步将发布/消费迁移至 Streams，或在 async-workers 中做兼容桥接。
- 保持对 Chat-AI 的最小侵入；后续可将 Chat-AI 消费方也迁至 Streams。

### gateway-python（可选）

- 如需前端统一走 8000：新增 HTTP SSE 代理至 dialog-engine；否则由 input-handler 直连 dialog-engine 内网地址。

---

## 7. 数据模型（M3）

SQLite（dialog-engine 本地）：

```sql
CREATE TABLE IF NOT EXISTS turns(
  sessionId TEXT,
  turn      INTEGER,
  role      TEXT CHECK(role IN ('user','assistant')),
  text      TEXT,
  ts        INTEGER,
  PRIMARY KEY(sessionId, turn, role)
);

CREATE TABLE IF NOT EXISTS outbox_events(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  type       TEXT,
  payload    TEXT,
  created_at INTEGER,
  delivered  INTEGER DEFAULT 0
);
```

---

## 8. 验收指标与测试

- 指标（日志含 `correlationId=sessionId#turn`）：
  - M1：文本首包（TTFT）P95 < 250ms。
  - M2：音频首包 P95 < 800ms；STOP→停止 < 100ms。
  - M3：Outbox 投递成功率 ≈ 100%，重试与积压可观测。
  - M4：连续播放稳定，无明显卡顿；句内打断成功率高。

- 测试（pytest + e2e）：
  - 单元：`memory_shortterm_test.py`、`chat_service_test.py`、`tts_streamer_test.py`、`ltm_outbox_test.py`。
  - e2e：
    - 启动 dialog-engine（LLM/TTS 使用 mock）；
    - Input POST 文本 → SSE 收到 `text-delta`；
    - 向 Output 注入 STOP → 验证后续不再收到分片；
    - 统计首包与端到端延迟。

---

## 9. 任务拆分（Issue 模板）

1) SVC-001 新增 `services/dialog-engine`（SSE 入口 + 健康检查）
2) SVC-002 `chat_service.py`（Redis 上下文读取 + 流式 LLM 模拟/真实）
3) SVC-003 Input Handler 增加 SSE 调用（Flag 控），失败回退
4) SVC-004 Output Handler 新增内部 WS `/ws/ingest/tts` + 中继
5) SVC-005 dialog-engine `tts_streamer.py`（分片/STOP，可先模拟）
6) SVC-006 指标埋点与 correlationId 贯穿
7) SVC-007 dialog-engine `memory_shortterm.py`（SQLite WAL）
8) SVC-008 Outbox + async-workers（Streams）
9) SVC-009 LTM/Analytics 迁移至 Streams 或桥接
10) SVC-010 e2e 测试脚本（首包/打断/背压）

---

## 10. 风险与回退

- 风险：
  - TTS 真流与句内打断复杂，提供商 API/库差异大；
  - 双路径并存期间的状态一致性与重复发送；
  - SSE/WS 在代理（Nginx/Docker 网络）下的长连接稳定性。
- 回退：
  - 关闭 `ENABLE_SYNC_CORE`/`SYNC_TTS_STREAMING`/`SYNC_TTS_BARGE_IN`，恢复旧链路；
  - 关闭 `ENABLE_STREAMS_OUTBOX`，恢复 Pub/Sub/列表。

---

## 11. 实施建议

- 优先在本机回环上连通 dialog-engine ↔ Output 内部 WS，减少网络变量；
- 打断优先实现“句边界停止”，再优化为“句内打断”；
- 统一内部/外部事件格式（SPEECH_CHUNK/control/done），降低重复代码；
- 日志与指标先行（TTFT、首音、STOP 响应时延、Outbox 重试）；
- 逐 Flag 渐进启用，每步都可回退。

---

本计划紧贴当前仓库服务与代码路径，尽量以“增量 + 低耦合”方式推进；在 M1-M2 即可显著降低文本/音频首包延迟并建立打断框架，M3-M4 完成可靠事件与真流式体验。


# ADR-0001: 同步主链路 + 异步扩展 重构计划（修订版）

Status: Proposed
Date: 2025-09-15
Author: Core Team

## 1. 背景与目标

现状：
- 主链路依赖 Redis 列表/发布订阅 在多服务间传递：`input-handler → memory → chat-ai → tts → output-handler`。
- `output-handler` 通过 Redis 频道接收“最终结果”，再以 WS 回推给前端，音频通过文件落地再分块发送，难以做到“首包快、连续流、可打断”。
- LTM 服务与 `chat-ai`、`memory` 通过 Pub/Sub 和列表交互，可靠性与可观测性有限。

目标（本次重构迭代）：
- 引入单进程 `dialog-engine` 承担“短期记忆 → LLM → TTS”主链路，改为“同步、流式、可打断”。
- 保留 `input-handler` 与 `output-handler`，以 Feature Flag 渐进切换。
- 异步扩展改用 Redis Streams（+ Outbox），提升可靠性与消费监控。
- 先实现“文本流 + 半流式 TTS 与打断雏形”，再进化为“真流 TTS 与句内打断”。

不在本次范围：
- 前端大改、3D/视觉模块、复杂插件生态；对外 HTTP 网关形态保持兼容。

## 2. 分阶段实施与里程碑

- M1（2–3 天）：
- 新增 `services/dialog-engine`（源码位于 `services/dialog-engine/src/dialog_engine/`），提供 `POST /chat/stream`（SSE）文本流；短期记忆可先用 SQLite WAL 或临时复用 Redis。
  - `input-handler` 在 Flag 开启时改为直调 `/chat/stream`（SSE），旧队列保留回退。
  - 输出侧暂维持现状：文本通过 SSE 提示渲染，音频仍走现有 TTS → 文件 → `output-handler` 分块回推。
  - 验收：SSE 首包文本 TTFT P95 < 300ms（以 mock LLM/降采样实现）。

- M2（2–4 天）：
  - `dialog-engine` 内增 `tts_streamer`（半流式：按句/短片段增量合成与推送）。
  - `output-handler` 新增“内部 WS”通道 `/ws/ingest` 接收 dialog-engine 推送的 `SPEECH_CHUNK`，并暴露 WS 内部回控（STOP）。
  - 引入停止（barge-in）控制：`output-handler` 将 STOP 通过该内部 WS 回传给 `dialog-engine`，实现“下一句前打断 → 句内打断（beta）”。
  - 验收：端到端首音延迟 P95 < 800ms；STOP 响应 < 100ms（内部 WS）。

- M3（2–4 天）：
  - 引入 Outbox + Redis Streams：`events.ltm`, `events.analytics`, `events.plugins`。新增 `async-workers` 消费组与监控。
  - LTM/Analytics 改造为消费 Streams（或先通过桥接兼容 Pub/Sub）。
  - 验收：事件送达率 100%，消费延迟与堆积监控可见。

- M4（3–6 天）：
  - Provider 真流化：改造 EdgeTTS（优先）/OpenAI provider，支持边生产边推送；打断即时生效（取消流/任务）。
  - Gateway 可选增加 SSE/WS 代理，以便前端统一走 8000 端口。
  - 验收：连续 1h 直播无致命错误；音频首包 P95 < 800ms；打断可靠。

回退：任意阶段可通过 Flag 关闭同步链路与 Streams，回退到旧路径。

## 3. 系统架构（修订）

- 同步主链路：`input-handler → dialog-engine(SSE) → output-handler(WS 中继)`。
- 异步扩展：`dialog-engine → Outbox(SQLite) → Redis Streams → async-workers → LTM/Analytics/Plugins`。

## 4. 服务改造明细

### 4.1 新增 dialog-engine（services/dialog-engine）

建议目录：
```
services/dialog-engine/
  Dockerfile
  requirements.txt
  src/
    dialog_engine/
      app.py              # FastAPI，POST /chat/stream（SSE），健康检查
      chat_service.py     # 上下文组装，调用 LLM（先 mock 或简化）
      ltm_outbox.py       # Outbox(SQLite) → Redis Streams
      tts_streamer.py     # 半流式/流式合成与打断（M2 先实现句边界）
      tts_providers/
        base.py
        mock.py
        edge_tts_provider.py
      __init__.py
  tests/
```

特性：
- SSE 文本流事件：`text-delta`, `control`, `done`。
- 向 `output-handler` 的“内部 WS”推送音频分片：`SPEECH_CHUNK`，并处理 STOP 回控。
- 事件投递采用 Outbox → Redis Streams，避免丢失。

### 4.2 Input Handler（services/input-handler-python）

- 新增 Flag：`ENABLE_SYNC_CORE=true` 时：
  - 文本输入：改为调用 `dialog-engine /chat/stream`（SSE）得到文本增量；仍将原始输入写入 Redis 供旧链路回退。
  - 音频输入：保持现有上传 → ASR → 桥接到文本路径；后续视需要直连 `dialog-engine` ASR 客户端（可选）。
- 失败/异常：回退到旧的 `user_input_queue` 路径。

### 4.3 Output Handler（services/output-handler-python）

- 保持对外 WS 协议不变（前端无需改动）。
- 新增“内部 WS”用于与 `dialog-engine` 通信：
  - `WS /ws/ingest` 接收：
    ```json
    {"type":"SPEECH_CHUNK","sessionId":"...","seq":1,"pcm":"<base64>","viseme":{}}
    ```
  - 同连接双向控制：
    ```json
    {"type":"CONTROL","action":"STOP","reason":"user_interrupt"}
    ```
  - 将接收到的音频实时中继给外部 WS（前端），保持现有兼容。
- 注：如果维持“文件落地 + 分块”一段时间，需兼容两种来源（内部 WS 与 Redis 文件路径）。

### 4.4 TTS 服务（services/tts-python）

- M1：保持现状（用于回退路径）。
- M2：在 `dialog-engine` 内实现 `tts_streamer`（半流式）。若需沿用现有 provider，可先按“句边界分段→push”。
- M4：provider 真流化（EdgeTTS 优先，使用其 stream 接口）。

### 4.5 Memory / Chat-AI / LTM

- 短期记忆迁入 `dialog-engine`（SQLite WAL，仅上下文窗口）。
- `memory-python` 与 `chat-ai-python` 保留运行一段时间以兼容旧链路；逐步减少耦合。
- LTM 服务改造为消费 Redis Streams（或先由桥接 worker 将 Streams 转发到现有 Pub/Sub 频道）。

### 4.6 Gateway（services/gateway-python）

- M1 可不改（input-handler 内网直调 dialog-engine）。
- 如需前端统一走 8000：新增 `POST /chat/stream` 反向代理至 dialog-engine（SSE 代理），以及“内部 WS”反向代理。

## 5. 接口契约

### 5.1 Input → dialog-engine（SSE）
- `POST /chat/stream`
- 请求：
```json
{
  "sessionId":"live-001",
  "turn":42,
  "type":"TEXT|ASR_FINAL|COMMAND",
  "content":"今晚玩什么？",
  "meta":{"lang":"zh"}
}
```
- SSE 事件：
  - `text-delta`: `{ "content":"…", "eos":false }`
  - `control`: `{ "action":"HINT_TTS_START" }`
  - `done`: `{ "stats": {"ttft_ms": 130, "tokens": 57} }`

### 5.2 dialog-engine ↔ Output（内部 WS）
- 下行音频：`SPEECH_CHUNK`（见 4.3）。
- 上行控制：`CONTROL(STOP)`；要求收到即刻停止后续推送并清空队列。

### 5.3 Redis Streams（异步）
- Streams：`events.ltm`, `events.analytics`, `events.plugins`。
- 消费组示例：`ltm-workers`, `a11y-workers`。
- Outbox 表：批量 XADD 成功后置 `delivered=1`。

## 6. 数据模型（SQLite）

```sql
-- 短期记忆（仅上下文窗口）
CREATE TABLE IF NOT EXISTS turns(
  sessionId TEXT,
  turn      INTEGER,
  role      TEXT CHECK(role IN ('user','assistant')),
  text      TEXT,
  ts        INTEGER,
  PRIMARY KEY(sessionId, turn, role)
);

-- 事件外发盒（Outbox）
CREATE TABLE IF NOT EXISTS outbox_events(
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  type       TEXT,
  payload    TEXT,
  created_at INTEGER,
  delivered  INTEGER DEFAULT 0
);
```

## 7. 配置与 Feature Flags

- `ENABLE_SYNC_CORE=true`：启用 `input → dialog-engine → output` 主链路（文本 SSE）。
- `SYNC_TTS_STREAMING=true`：启用半流式/流式 TTS 推送（M2+）。
- `SYNC_TTS_BARGE_IN=true`：允许打断。
- `ENABLE_ASYNC_EXT=true`：启用 Outbox + Streams。
- `ENABLE_LTM_INLINE=false`：按需同步召回 LTM（默认关）。

## 8. 测试与验收

- 单元：
  - `memory_shortterm`: 并发写入一致性（WAL），裁剪到最近 N 轮。
  - `chat_service`: 上下文组装与文本流（mock LLM）。
  - `tts_streamer`: 分段合成、STOP 响应 < 100ms。
  - `ltm_outbox`: Outbox → Streams → 标记 delivered。
- E2E：
  - 文本输入 → SSE 首包 < 300ms（mock LLM）；
  - 半流式音频输出首包 < 800ms；
  - 发送 STOP 后不再收到新的分片；
  - Streams 消费稳定无丢失。

验收：连续两场 1h 演示无致命错误；日志贯穿 `correlationId=sessionId#turn`；指标稳定。

## 9. 安全与回退
- 任意阶段可将 `ENABLE_SYNC_CORE=false` 回退旧主链路。
- SSE/WS 通道限本地/内网暴露；校验 `sessionId` 与速率限制。
- Outbox 落盘保证事件可靠送达；消费者组监控堆积。

## 10. 任务拆分（Issue 模板）
1) SVC-001 新增 dialog-engine（SSE 入口 + 健康检查）
2) SVC-002 短期记忆 SQLite(WAL) 与上下文窗口
3) SVC-003 chat_service：文本流（mock LLM）+ Outbox 事件
4) SVC-004 tts_streamer：半流式/句边界 + STOP 协议
5) SVC-005 output-handler 内部 WS `/ws/ingest` 与中继
6) SVC-006 Outbox → Redis Streams + workers
7) SVC-007 input-handler Flag 接入 `/chat/stream`
8) SVC-008 gateway（可选）SSE/WS 代理
9) SVC-009 e2e：首包、打断、背压脚本

备注：以上按 M1→M4 分批合入，保持旧路径可用与可回退。

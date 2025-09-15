# ADR-0002 Redis 键空间规划与迁移方案

本方案明确重构后 Redis 的职责、键前缀规范、保留/迁移清单、Streams 与 Outbox 的使用方式、限流与分布式协调键，以及回退策略。目的：在引入 SQLite 负责对话上下文与 Outbox 后，Redis 转型为“事件总线与跨进程协调层”，保障可靠、可观测与可回退。

---

## 1. 角色定位（重构后）

- 事件总线：
  - Redis Streams（主）用于 LTM/Analytics/Plugins 等异步事件，结合 Outbox 提升可靠投递。
  - Pub/Sub 与 列表（过渡/回退）保留至新链路稳定。
- 分布式协调：
  - 限流、熔断、互斥锁、去重幂等、在场状态（presence）、背压计数、短期缓存等。

SQLite：承担 dialog-engine 的“短期上下文窗口”和“Outbox 缓冲”。Postgres/pgvector：承担 LTM 持久化与向量检索。

---

## 2. 现有键/通道清单（现状）

- 列表（Lists）
  - `user_input_queue`（Input→Memory）
  - `asr_tasks`（Input→ASR）
  - `ltm_requests`（Chat-AI→LTM 请求）
- 发布/订阅（Pub/Sub）
  - `asr_results`（ASR→Input 桥接）
  - `ai_responses`（Chat-AI→Memory 回写 AI 回复）
  - `ltm_responses`（LTM→Chat-AI 搜索响应）
  - `task_response:{task_id}`（TTS→Output 向前端转发）
  - `memory_updates`（Memory→Chat-AI/LTM：用户/AI 消息事件）

以上将作为“旧主链路/兼容路径”保留一段时间，供回退与迁移期桥接。

---

## 3. 新增与迁移（重构后主推）

### 3.1 Streams 定义

- 事件流（持久消费，配消费者组）
  - `events.ltm`（长期记忆写入/摘要/embedding）
  - `events.analytics`（观测与指标）
  - `events.plugins`（可选：插件/情感/工具事件）

消费者组示例：
- `events.ltm` → 组名：`ltm-workers`
- `events.analytics` → 组名：`a11y-workers`
- `events.plugins` → 组名：`plugins-workers`

创建命令（初始化脚本执行一次）：
```
XGROUP CREATE events.ltm ltm-workers $ MKSTREAM
XGROUP CREATE events.analytics a11y-workers $ MKSTREAM
XGROUP CREATE events.plugins plugins-workers $ MKSTREAM
```

读取示例：
```
XREADGROUP GROUP ltm-workers worker-1 COUNT 16 BLOCK 2000 STREAMS events.ltm >
```

长度控制：`XADD ... MAXLEN ~ 100000`（近似裁剪）。

### 3.2 Outbox 映射（在 dialog-engine 内）

- SQLite 表 `outbox_events(id, type, payload, created_at, delivered)`
- 后台投递：扫描 `delivered=0` → `XADD events.<topic> * type=<type> payload=<json>` → 成功后 `delivered=1`
- 失败重试：指数退避 + 死信日志；不丢失（以 SQLite 为准）。

事件载荷建议（统一信封）：
```
{
  "correlationId": "<sessionId>#<turn>",
  "sessionId": "live-001",
  "turn": 42,
  "type": "LtmWriteRequested|AnalyticsEvent|...",
  "payload": { ... },
  "ts": 1736900000
}
```

### 3.3 兼容与桥接（迁移策略）

- `memory_updates` → `events.ltm`：
  - M3 起 dialog-engine 直接写 `events.ltm`（Outbox）；
  - 过渡期可提供桥接 worker：监听 `events.ltm`，生成兼容的 `memory_updates`（Pub/Sub）以不影响旧消费者；反向桥接按需。
- `ltm_requests`/`ltm_responses`（列表+Pub/Sub）→ Streams：
  - 维持现状作为“类 RPC”；后续可迁为 `rpc.ltm.requests`（Stream）+ 响应走 Pub/Sub 指定 `response_channel` 或基于请求 ID 的临时 Stream（复杂度较高，后续评估）。
- `task_response:{task_id}`（Pub/Sub）：
  - 保留为 Output 回退通道；新链路下 dialog-engine→Output 走内部 WS 流式，稳定后再考虑收敛格式。

---

## 4. 分布式协调与缓存键（长期保留）

- 限流/熔断
  - `rate_limit:{provider}:{window}` → 计数器（TTL=窗口大小），超限降级或排队。
  - `circuit_breaker:{provider}` → 熔断状态（TTL 短、带半开探测）。
- 互斥与幂等
  - `lock:session:{sessionId}` → 讲话/播放互斥（TTL=会话超时，设 NX）。
  - `idempotency:{correlationId}` → 处理去重（TTL=几分钟）。
- 在场/背压
  - `presence:session:{sessionId}` → 最近活跃心跳（TTL=60s）。
  - `metrics:queue:{name}:depth` / `metrics:drop:*` → 统计与报警。
- 缓存/配置
  - `cache:ltm:{hash}` → LTM 检索结果短缓存（TTL=60–120s）。
  - `cfg:voice:{sessionId}` → 音色/速率等个性化参数（TTL=可配置）。

TTL 与刷新策略应按使用场景最小化“脏数据停留时间”。

---

## 5. 命名与规范

- 前缀与语义
  - 事件流：`events.<domain>`（ltm/analytics/plugins）
  - RPC/请求流（如采用）：`rpc.<service>.<topic>`
  - 配置：`cfg.*`，缓存：`cache.*`，指标：`metrics.*`，锁：`lock.*`，幂等：`idempotency.*`，在场：`presence.*`。
- ID 关联
  - `correlationId` 统一为 `<sessionId>#<turn>`，贯穿日志与事件。
- MAXLEN 与保留
  - 事件流控制在 1e5 级，冷数据由下游持久化（如 Postgres/pgvector）。

---

## 6. 观测与运维

- Streams 健康：
  - `XINFO STREAM events.ltm` 查看长度、last-entry；
  - `XPENDING events.ltm ltm-workers` 查看积压；
  - 消费者心跳：定期 `XACK` + 监控 `idle` 字段。
- Outbox 健康：
  - 监控 SQLite `outbox_events` 中 `delivered=0` 的条数与滞留时长；
  - 投递失败分布与重试次数。
- 回退演练：
  - 通过 Feature Flags 关闭同步链路/Streams，验证旧链路是否仍能完整工作。

---

## 7. Feature Flags（与迁移相关）

- `ENABLE_SYNC_CORE`：Input→dialog-engine（SSE）。
- `SYNC_TTS_STREAMING` / `SYNC_TTS_BARGE_IN`：内部 WS 音频分片与打断。
- `ENABLE_STREAMS_OUTBOX`：启用 Outbox + Streams 投递；关闭时恢复旧的 Pub/Sub/列表。
- `ENABLE_LTM`：是否启用 LTM 检索（现状：Chat-AI 通过列表/频道；后续迁 Streams）。

---

## 8. 安全与合规

- 事件载荷避免包含敏感原文（必要时脱敏/摘要）；
- 键名不包含用户私密标识（使用 `sessionId`、`correlationId` 即可）；
- Streams 持久化的窗口有限，长久数据落地到专用持久化存储（Postgres/pgvector）。

---

## 9. 回退策略

- 任一阶段均可：关闭 `ENABLE_SYNC_CORE`/`ENABLE_STREAMS_OUTBOX`，回到旧链路（`user_input_queue`、`memory_updates`、`task_response:{task_id}` 等）。
- 桥接 worker 可双写或双读，确保迁移期间旧消费者不受影响。

---

## 10. 清单速览（保留 vs 迁移）

- 保留（回退/兼容）：
  - 列表：`user_input_queue`、`asr_tasks`、`ltm_requests`
  - 频道：`asr_results`、`ai_responses`、`ltm_responses`、`task_response:{task_id}`、`memory_updates`
- 迁移（主推）：
  - Streams：`events.ltm`、`events.analytics`、（可选）`events.plugins`
  - 协调键：`rate_limit:*`、`lock:*`、`idempotency:*`、`presence:*`、`metrics:*`、`cache:*`、`cfg:*`

本方案与 ADR-0001 同步实施，先引入 Outbox+Streams 与内部 WS，逐步迁移旧键，确保每一步都可回退且可观测。


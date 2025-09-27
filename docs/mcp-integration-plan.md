# MCP 工具集成方案

## 概述

本文档基于当前 `dialog-engine` 架构，详细说明如何在 Free-Agent-Vtuber 项目中引入 [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol) 工具能力。方案目标是：

- **对话流畅**：在保持现有 SSE 流式对话体验的前提下，透明地插入工具调用结果；
- **模块解耦**：通过 Redis Streams 将工具请求路由到独立的 `plugins-mcp` 模块，符合项目 ADR 的异步扩展方向；
- **可靠可观测**：使用 Outbox + 消费组模式确保投递可靠，提供监控点和超时退避机制。

## 1. 现状分析

### 1.1 对话引擎链路

- `services/dialog-engine` 的 `ChatService.stream_reply` 负责拼接短期记忆、长期记忆和用户输入，调用 `OpenAIChatClient.stream_chat` 获取流式响应，并通过 SSE 将增量返回前端。
- `OpenAIChatClient.stream_chat` 已经能捕获增量中的 `delta.tool_calls`，但目前仅在“纯工具调用”场景下抛出 `LLMStreamEmptyError`，上层通过异常感知到工具调用。
- Redis Outbox/Streams 机制已部署，`events.plugins` 流在 ADR 中预留给未来的插件或工具扩展。

### 1.2 事件与异步能力

- `dialog-engine` 将需要异步处理的事件写入 SQLite Outbox，再异步刷到 Redis Streams（如 `events.ltm`、`events.analytics`）。
- `services/async-workers` 示例展示了如何使用消费组消费这些流。
- 现有的上下文检索（如 `fetch_ltm_context`）使用 Redis 列表 + 请求 ID 实现 RPC 式等待，可复用到 MCP 响应的回传逻辑。

## 2. 设计原则

1. **同步链路最小侵入**：`ChatService` 在发现 LLM 工具调用时暂停文本输出、发起工具请求、等待结果，再继续生成回答。
2. **异步模块化**：所有 MCP 调用由新建的 `plugins-mcp` 模块处理，通过 Redis Streams 与主链路通信，保持可独立部署和扩缩容。
3. **可靠传输**：沿用 Outbox + Streams + 消费组的“至少一次”语义，必要时借助幂等键避免重复执行。
4. **可配置与可观测**：通过环境变量开关 MCP，暴露监控指标（队列积压、超时次数等）。

## 3. 整体架构

```
┌────────────────────┐       tool call       ┌────────────────────┐
│  dialog-engine     │ ───────────────────▶ │    events.plugins   │
│  (ChatService)     │                       └────────────────────┘
│   ▲          ▼      tool response RPC       ▲              │
│   │  SSE     │ ◀─────────────────────────── │              ▼
└───┼──────────┘                               │    ┌──────────────────┐
    │                                          └──▶│ plugins-mcp worker │
    │                ┌────────────────────┐          │  (MCP Client)   │
    └──────────────▶│ OpenAIChatClient   │◀─────────┴──────────────────┘
                     └────────────────────┘
```

- `ChatService` 负责从 LLM 捕获工具调用、发送事件、等待结果并继续补全。
- `plugins-mcp` 消费 `events.plugins`，调用 MCP 工具，写回响应流或 Pub/Sub。
- Redis 负责请求转发和响应同步，保持模块边界清晰。

## 4. 模块改造计划

### 4.1 扩展 LLM 客户端（`services/dialog-engine`）

1. **调整 `OpenAIChatClient.stream_chat`**
   - 在流式循环中一旦检测到 `tool_calls`，收集 `tool_call_id`、`function.name`、`arguments`。
   - 通过新增的控制事件（例如 `ToolCallEvent`）向上层返回，而非仅在异常分支中处理。
   - 保留 `LLMStreamEmptyError` 以兼容旧逻辑，但推荐上层走新事件接口。

2. **更新 `ChatService.stream_reply`**
   - 监听流式生成中的控制事件，暂停向 SSE 推送文本。
   - 将 `tool_call` 信息写入 Outbox，落地到 `events.plugins`。
   - 向前端发送一个 `control` SSE（例如 `{type: "tool", status: "pending", toolName: ...}`）提示用户正在调用工具。

### 4.2 Outbox 与 Redis Streams 路由

1. 在 `ltm_outbox._stream_for_type`（或等价的流路由配置）中添加 `PluginToolCallRequested` → `events.plugins` 映射。
2. 设计事件载荷：
   ```json
   {
     "eventType": "PluginToolCallRequested",
     "correlationId": "<uuid>",
     "sessionId": "...",
     "turn": 42,
     "toolCallId": "call_abc",
     "toolName": "search",
     "arguments": {"query": "..."},
     "responseChannel": "rpc.plugins.responses:<uuid>"
   }
   ```
3. 写入 Outbox 后由后台任务刷入 `events.plugins`，保证可靠投递。

### 4.3 新建 `plugins-mcp` 模块

- 目录建议：`services/plugins-mcp/`，包含：
  - `main.py`：入口，创建 Redis 连接，加入消费组 `plugins-workers`。
  - `mcp_client.py`：封装与 MCP Server 的连接、鉴权和工具调用逻辑。
  - `config.py`：读取环境变量（`ENABLE_MCP`, `MCP_SERVER_ENDPOINT`, `MCP_REQUEST_TIMEOUT_MS` 等）。
  - `Dockerfile`、`requirements.txt`、`README.md`。

- 核心流程：
  1. `XREADGROUP` 订阅 `events.plugins`，批量拉取请求。
  2. 基于 `toolName` 映射到 MCP 工具并调用，传入 `arguments`。
  3. 获取 MCP 返回值后，通过 `XADD rpc.plugins.responses` 或 Redis Pub/Sub 发送响应消息，包含 `correlationId` 和 `toolCallId`。
  4. 使用 `XACK` 标记消息已处理；异常时记录日志并视情况重试或发送失败事件。

### 4.4 工具结果回传与继续推理

1. `ChatService` 在派发请求后，参考 `fetch_ltm_context` 的模式阻塞等待：
   - 监听 `responseChannel`，设置超时（如 10~15 秒）。
   - 支持重试或超时回退（例如通知用户“工具响应超时”）。
2. 收到结果后，将其写入对话上下文：
   ```python
   messages.append(
       ChatCompletionMessage(
           role="tool",
           content=result_text,
           tool_call_id=tool_call_id,
       )
   )
   ```
3. 再次调用 `OpenAIChatClient.stream_chat`，继续处理后续输出；若 LLM 再次请求工具，循环上述流程直到完成。

### 4.5 配置与监控

- 新增环境变量：
  - `ENABLE_MCP`（bool）：开启后才会派发请求，否则直接将工具调用作为失败处理。
  - `MCP_SERVER_ENDPOINT`、`MCP_API_KEY`：连接 MCP 服务所需信息。
  - `MCP_REQUEST_TIMEOUT_MS`、`MCP_MAX_RETRIES`：控制请求超时与重试。
- 指标采集：
  - Redis `XPENDING events.plugins`：消费积压。
  - 工具调用成功率、平均耗时。
  - 超时/异常计数。
- 日志：`correlationId` 串联 `dialog-engine` 与 `plugins-mcp` 之间的日志，便于排查。

## 5. 开发迭代计划

| 阶段 | 目标 | 关键输出 |
| ---- | ---- | -------- |
| Phase 1 | 梳理接口，扩展 `OpenAIChatClient` 和 `ChatService` 支持控制事件 | 单元测试覆盖工具事件；控制 SSE 消息格式草案 |
| Phase 2 | 打通 Outbox → Redis 流 → `plugins-mcp` 的消息链路 | 新模块雏形，能消费请求并将结果写回（可先用假 MCP 客户端） |
| Phase 3 | 集成真实 MCP SDK，补充配置和重试、超时处理 | 工具调用可闭环返回；集成测试验证多轮调用 |
| Phase 4 | 观测性与上线准备 | 指标、日志、告警配置；撰写运维手册 |

## 6. 风险与缓解

| 风险 | 说明 | 缓解措施 |
| ---- | ---- | -------- |
| 工具调用延迟导致 SSE 断流 | MCP 响应时间过长 | 设置合理超时，超时后回退到文字解释或提示稍后再试 |
| 消息重复消费 | Redis Streams 至少一次语义 | 使用 `correlationId` + `toolCallId` 做幂等校验，重复请求直接返回缓存结果 |
| MCP 工具鉴权或配置信息泄露 | 新增配置需要安全存储 | 通过 `.env` + Secrets 管理，禁止硬编码；上线前安全评审 |
| 多轮工具调用复杂度上升 | LLM 可能连续触发工具 | 在 `ChatService` 中用循环处理，并记录调用次数，必要时限制最大工具调用次数 |

## 7. 下一步工作

1. 确认 MCP 目标工具清单与鉴权方式，完成 PoC。
2. 在 `dialog-engine` 中实现控制事件管道并补充测试。
3. 创建 `plugins-mcp` 模块骨架，引入 MCP SDK（或自研客户端）。
4. 搭建开发环境（Docker Compose）联调：验证从 LLM 工具调用到 MCP 响应的全链路。
5. 补充文档（运行手册、故障排查指南）并准备上线评审。

---

本方案通过 Redis Streams 实现与 MCP 工具的解耦集成，既保留了现有对话链路的实时性，又为未来扩展更多插件能力奠定了基础。

# 项目后端架构图

本图展示了 Free Agent Vtuber 当前的后端服务协作方式，覆盖实时会话链路、TTS 推流控制以及长期记忆的异步扩展：

- 客户端统一通过 `API Gateway` 建立 WebSocket 连接，由网关分别代理到输入与输出服务，并负责 STOP 控制指令的下行。
- `Input Handler` 直接调用 `dialog-engine` 的文本（SSE）与语音接口，并在本地暂存上传数据，最终将会话结果发布到 Redis `task_response:{task}` 通道。
- `Dialog Engine` 内聚 ASR、短期记忆、LLM 对话和可选的同步 TTS 推流逻辑，同时将上下文与统计事件写入 SQLite Outbox，并投递到 Redis Streams 供异步任务消费。
- `Output Handler` 订阅 Redis 中的响应通道，向前端回推文本与音频；当启用同步 TTS 时，通过内部 WebSocket 与 `dialog-engine` 交换语音分片与 STOP 信号。
- `Async Workers` 及 `long-term-memory` 服务消费 Redis Streams / PubSub，负责长期记忆入库、向量检索以及分析统计等后台任务；旧的 `memory-python` 服务仍可通过队列桥接方案兼容历史流程。

```mermaid
graph TD
  subgraph Client["Client"]
    FE["前端 (Web / 桌面客户端)"]
  end

  subgraph GatewayLayer["接入层"]
    APIGW["API Gateway<br/>services/gateway-python"]
  end

  subgraph SyncPipeline["实时会话链路"]
    IH["Input Handler<br/>services/input-handler-python"]
    DE["Dialog Engine<br/>services/dialog-engine"]
    OH["Output Handler<br/>services/output-handler-python"]
  end

  subgraph DataInfra["状态与消息基础设施"]
    Redis[("Redis<br/>Pub/Sub + Streams")]
    STM[("SQLite<br/>短期记忆 / Outbox")]
    TempFS[("本地临时存储<br/>/tmp/aivtuber_tasks")]
    Mem0[("Mem0 / 向量存储")]
  end

  subgraph AsyncOps["异步扩展"]
    Workers["Async Workers<br/>services/async-workers"]
    LTM["Long-term Memory Service<br/>services/long-term-memory-python"]
    MEMSVC["Memory Service<br/>services/memory-python<br/>(兼容队列)"]
  end

  FE -- "WebSocket /ws/input" --> APIGW
  FE <-- "WebSocket /ws/output/{task}" -- APIGW

  APIGW -- "WS 代理" --> IH
  APIGW -- "WS 代理" --> OH
  APIGW -- "HTTP /control/stop" --> OH

  IH -- "HTTP(S) /chat/stream<br/>SSE 文本增量" --> DE
  IH -- "HTTP(S) /chat/audio<br/>ASR + 回复" --> DE
  IH -- "临时文件落盘" --> TempFS

  DE -- "推流 WS /ws/ingest/tts<br/>(SYNC_TTS_STREAMING)" --> OH
  OH -- "STOP / CONTROL" --> DE

  IH -- "PUBLISH task_response:{task}" --> Redis
  Redis -- "订阅 task_response:{task}" --> OH
  OH -- "WebSocket 推送" --> FE

  DE -- "短期记忆写入" --> STM
  DE -- "Outbox events.ltm / events.analytics" --> Redis

  Redis -- "Streams 消费" --> Workers
  Workers -- "派发记忆/分析任务" --> LTM

  LTM -- "memory_updates 订阅<br/>ltm_requests 消费" --> Redis
  LTM -- "Mem0 API<br/>向量入库/检索" --> Mem0

  DE -. "可选 LTM 检索<br/>HTTP /v1/memory/retrieve" .-> LTM

  IH -. "兼容：user_input_queue" .-> MEMSVC
  MEMSVC -. "memory_updates / ai_responses" .-> Redis
```

> 更新于：2025-10-02

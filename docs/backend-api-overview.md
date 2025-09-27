# 后端接口总览

本文档汇总当前各个后端服务（API Gateway、Input Handler、Output Handler、Manager UI 等）对外提供的接口，供前端和运维同学查询。除非特别说明，所有返回体均为 `application/json`，字符编码为 UTF-8。

## 服务与基础地址

| 服务 | 模块路径 | 默认端口 | 说明 | 推荐访问方式 |
| --- | --- | --- | --- | --- |
| API Gateway | `services/gateway-python` | `8000` | 前端统一入口，负责 WebSocket 代理、控制指令转发、ASR 任务入队 | 前端统一连接 `http(s)://<gateway-host>:8000`
| Input Handler | `services/input-handler-python` | `8001` | 直接处理用户输入的原始服务，通常通过 Gateway 访问 | 仅测试/排查时直连
| Output Handler | `services/output-handler-python` | `8002` | 负责向前端推送 AI 文本+音频结果，支持内部 TTS 推流 | 通过 Gateway 代理访问
| Manager UI | `manager` | `5000` | 后端服务管理界面与日志 API | 后台运维使用

---

## 1. API Gateway（端口 8000）

### 1.1 WebSocket 接口

#### `GET ws(s)://<gateway>/ws/input`
- **用途**: 上传用户输入（文本 / 录音）；成功后触发下游处理流程。
- **握手与首包**:
  1. 连接建立后，服务器发送任务分配消息：
     ```json
     {"type":"system","action":"task_id_assigned","task_id":"<uuid>"}
     ```
  2. 前端应缓存 `task_id`，用于后续结果订阅。
- **上传流程**:
  1. 发送 JSON 元数据：
     ```json
     {"type":"text"|"audio","chunk_id":0,"action":"data_chunk"}
     ```
  2. 紧接着发送对应的二进制数据块（文本需使用 UTF-8 编码）。
  3. 重复步骤 1-2 直至所有块发送完成。
  4. 发送完成指令：`{"action":"upload_complete"}`。
  5. 服务端确认入队：
     ```json
     {"type":"system","action":"upload_processed","status":"queued","task_id":"<uuid>"}
     ```
- **错误处理**: 如分片顺序异常会返回字符串错误，如 `"Chunk ID mismatch: expected 2, got 0"`。

#### `GET ws(s)://<gateway>/ws/output/{task_id}`
- **用途**: 订阅指定任务的处理结果。
- **前置条件**: `task_id` 必须是已通过输入通道获得的合法 UUID。
- **数据顺序**:
  1. 文本结果：
     ```json
     {"status":"success","task_id":"<uuid>","content":"AI 回复文本","audio_present":true|false}
     ```
  2. 若包含音频，服务器按以下循环发送：
     - 音频块元数据：`{"type":"audio_chunk","task_id":"<uuid>","chunk_id":0,"total_chunks":N}`
     - 立刻跟随对应的二进制音频数据。
  3. 全部块发送结束后：`{"type":"audio_complete","task_id":"<uuid>"}`。
  4. 如出现错误，则推送：`{"status":"error","error":"..."}`。

### 1.2 HTTP 接口

| 方法 & 路径 | 说明 | 请求体 | 成功响应 | 备注 |
| --- | --- | --- | --- | --- |
| `POST /control/stop` | 代为向 Output Handler 转发停止指令 | `{ "sessionId": "<uuid>" }` | 透传下游响应；成功示例：`{"ok": true}` | `400` 缺少 `sessionId`; `502`/`409` 见 Output Handler 行为 |
| `POST /api/asr` | 将本地 WAV 文件路径入队，触发 ASR | `{ "path": "/abs/path.wav", "options": {"lang":"zh","timestamps":true} }` | `{ "task_id": "<uuid>" }` | 仅 MVP；需绝对路径 |
| `GET /internal/output/health` | 代理 Output Handler 健康检查 | 无 | 透传下游 JSON 或 `{status_code, body}` | 调试用 |
| `GET /health` | 网关健康状态 | 无 | `{ "status": "ok", "gateway": "running", ... }` | 监控用 |
| `GET /connections` | 查看当前连接数 | 无 | `{ "total_connections": 0, "connections": [] }` | 仅调试 |
| `GET /` | 简易状态页 (HTML) | 无 | 静态 HTML | 浏览器查看 |

---

## 2. Input Handler（端口 8001）

> 前端默认通过 Gateway 访问。直接连入仅用于定位问题。

### 2.1 WebSocket

`GET ws(s)://<input-handler>/ws/input`
- 协议与 Gateway `/ws/input` 完全一致。
- 服务器端口的默认响应同 Gateway（含任务 ID、上传确认）。

### 2.2 HTTP

`GET /`
- 返回 HTML 自检页，包含服务说明与当前活跃连接数。

---

## 3. Output Handler（端口 8002）

### 3.1 WebSocket

#### `GET ws(s)://<output-handler>/ws/output/{task_id}`
- 协议与 Gateway `/ws/output/{task_id}` 一致。

#### `GET ws(s)://<output-handler>/ws/ingest/tts`
- **用途**: 内部通道，供对话引擎推送流式 TTS PCM 块。
- **消息类型**:
  - `{"type":"SPEECH_CHUNK","sessionId":"<uuid>","seq":0,"pcm":"<base64>"}` → 会被转发给对应前端。
  - `{"type":"CONTROL","action":"END"|"STOP_ACK","sessionId":"<uuid>"}` → 向前端发送控制消息。
- 默认要求环境变量 `SYNC_TTS_STREAMING=true` 才会接受连接，否则返回 4403。

### 3.2 HTTP 接口

| 方法 & 路径 | 说明 | 请求体 | 成功响应 | 错误 |
| --- | --- | --- | --- | --- |
| `POST /control/stop` | （实验）向上游 dialog-engine 发送 STOP 指令 | `{ "sessionId": "<uuid>" }` | `{ "ok": true }` | `400` 缺参；`409` 未启用撞线 (`SYNC_TTS_BARGE_IN` 关闭)；`503` 未连上游；`500` 推送失败 |
| `GET /status/{task_id}` | 查询任务连接状态 | 无 | `{ "task_id": "...", "status": "connected"|"waiting"|"completed"|"not_found", "connected": true|false }` | - |
| `GET /health` | 健康检查 | 无 | `{ "status": "ok", "redis": "connected", ... }` | - |
| `GET /` | HTML 信息页 | 无 | 服务说明 | - |

---

## 4. Manager UI（端口 5000）

### 4.1 页面

- `GET /` — 返回管理页面 HTML。

### 4.2 服务控制 API

| 方法 & 路径 | 功能 | 请求体 | 响应示例 |
| --- | --- | --- | --- |
| `GET /api/services` | 列出所有可管控服务及其状态 | 无 | `[ {"id":"gateway-python","name":"网关模块","status":"running"}, ... ]` |
| `POST /api/services/<service_id>/start` | 启动指定服务 | 无 | `{ "success": true, "message": "服务启动成功" }` |
| `POST /api/services/<service_id>/stop` | 停止指定服务 | 无 | `{ "success": true, "message": "服务停止成功" }` |
| `GET /api/services/<service_id>/status` | 查询服务是否在运行 | 无 | `{ "status": "running" }` |

### 4.3 日志 API

| 方法 & 路径 | 功能 | 响应格式 |
| --- | --- | --- |
| `GET /api/logs` | 获取所有服务最近 500 条日志 | `[ {"timestamp": "2025-02-01 10:00:00", "service_id": "gateway-python", "message": "...", "type": "stdout"}, ... ]` |
| `GET /api/logs/<service_id>` | 获取单个服务日志 | 同上 |
| `GET /api/logs/stream` | Server-Sent Events 实时日志 | SSE：`data: {...}\n\n`，空闲 1 秒发送心跳 `{"type":"heartbeat"}` |
| `POST /api/logs/clear/<service_id>` | 清空指定服务日志 | `{ "success": true }` |
| `POST /api/logs/clear` | 清空全部日志 | `{ "success": true }` |

---

## 5. 内部事件总线（Redis）参考

> 以下为服务间通信使用的队列与频道，前端通常无须直接操作，但有助于理解链路。

| 名称 | 类型 | 生产方 | 消费方 | 数据示例 |
| --- | --- | --- | --- | --- |
| `user_input_queue` | 列表 | Input Handler | Memory Service | `{ "task_id": "...", "type": "text", "content": "..." }`
| `task_response:{task_id}` | 频道 | Chat AI / TTS | Output Handler | `{ "text": "...", "audio_file": "/tmp/.../output.mp3" }`
| `asr_tasks` | 列表 | Gateway/Input Handler | ASR Service | `{ "task_id": "...", "audio": {"path": "/abs/file.wav"} }`
| `asr_results` | 频道 | ASR Service | Input Handler | `{ "task_id": "...", "status": "finished", "text": "..." }`
| `memory_updates` | 频道 | Memory Service | Chat AI / LTM | `{ "user_id": "...", "content": "...", "require_ai_response": true }`
| `ai_responses` | 频道 | Chat AI | Memory Service | `{ "user_id": "...", "text": "..." }`
| `ltm_requests` | 列表 | Chat AI | Long-Term Memory | `{ "request_id": "...", "type": "search", "data": {"query": "..."} }`
| `ltm_responses` | 频道 | Long-Term Memory | Chat AI | `{ "request_id": "...", "success": true, "memories": [...] }`
| `tts_requests` | 列表 | Chat AI | TTS Service | `{ "task_id": "...", "text": "...", "response_channel": "task_response:..." }`
| `tts_errors` (`config.tts.error_channel`) | 频道 | TTS Service | 监控 | `{ "status": "error", "error": {"code": "..."} }`

---

## 6. 常用环境变量与说明

| 变量 | 默认值 | 作用范围 | 说明 |
| --- | --- | --- | --- |
| `INPUT_HANDLER_URL` | `ws://localhost:8001` | Gateway | 指向输入处理服务的 WebSocket 地址 |
| `OUTPUT_HANDLER_URL` | `ws://localhost:8002` | Gateway | 指向输出处理服务的 WebSocket 地址 |
| `REDIS_HOST` / `REDIS_PORT` | `localhost` / `6379` | 多数服务 | Redis 连接配置 |
| `SYNC_TTS_STREAMING` | `false` | Output Handler | 是否允许 `/ws/ingest/tts` 推流 |
| `SYNC_TTS_BARGE_IN` | `false` | Output Handler | 是否允许 `POST /control/stop` 触发撞线 |
| `ENABLE_SYNC_CORE` | `false` | Input Handler | 文本输入是否直连对话引擎（SSE） |
| `ENABLE_LTM` | `false` | Chat AI | 是否启用长期记忆检索链路 |

---

## 7. 接口使用建议

1. **前端生产路径**：仅需连接 Gateway 的 `/ws/input` 与 `/ws/output/{task_id}`，其他接口可通过 HTTP 调用（如 `/control/stop`）。
2. **任务生命周期**：同一个 `task_id` 应在输入确认后立即建立输出连接，避免超时（默认 5 分钟）。
3. **音频处理**：目前输出音频为 MP3，务必按照 `chunk_id` 顺序累积并在 `audio_complete` 后合并。
4. **错误兜底**：若输出连接收到 `status=error`，前端可提示“系统繁忙”并允许用户重试。
5. **调试排查**：可通过 Manager UI 查看服务状态、拉取实时日志，或直接访问各服务的 `/health` 端点确认连通性。

> 文档最后更新：2025-09-27（请在修改接口后同步更新此文档）。

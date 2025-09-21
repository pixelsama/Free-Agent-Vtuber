# 前端与后端接口契约

本文档从代码实现出发，梳理当前前端通过网关（gateway-python）访问的全部对接接口，以及与输入服务、输出服务之间的数据交换协议。请在对前端进行重构时以此为准，README 等旧文档可能已过时。

## 总览

| 能力 | 协议 | 网关入口 | 目标服务/说明 |
| ---- | ---- | -------- | ------------- |
| 发送文本/音频输入 | WebSocket | `ws://<gateway>/ws/input` | 代理到 input-handler (`/ws/input`) [`services/gateway-python/main.py:153`](services/gateway-python/main.py:153) |
| 订阅任务结果（文本+音频） | WebSocket | `ws://<gateway>/ws/output/{task_id}` | 代理到 output-handler (`/ws/output/{task_id}`) [`services/gateway-python/main.py:159`](services/gateway-python/main.py:159) |
| 强制打断当前 TTS（可选） | HTTP POST | `POST /control/stop` | 转发到 output-handler 的同名接口 [`services/gateway-python/main.py:178`](services/gateway-python/main.py:178) |
| 输出服务健康检查 | HTTP GET | `GET /internal/output/health` | 拉取 output-handler `/health` [`services/gateway-python/main.py:210`](services/gateway-python/main.py:210) |
| 网关自检/连接数 | HTTP GET | `/health`, `/connections` | 网关本地信息 [`services/gateway-python/main.py:268`](services/gateway-python/main.py:268), [`services/gateway-python/main.py:278`](services/gateway-python/main.py:278) |
| 离线 ASR 任务投递（仅文件路径） | HTTP POST | `POST /api/asr` | 直接在网关内使用 Flask Blueprint 入队 Redis [`services/gateway-python/src/services/asr_routes.py:28`](services/gateway-python/src/services/asr_routes.py:28) |

下文详细描述各接口的消息流程与字段约束。

## WebSocket `/ws/input`

**会话建立**
1. 网关接受前端连接后会立即转连 input-handler，并返回 `task_id` 分配消息 [`services/input-handler-python/main.py:68`](services/input-handler-python/main.py:68)。前端在 `connectInput` 中等待此消息并自动启动输出通道 [`front_end/src/composables/useApi.js:102`](front_end/src/composables/useApi.js:102)。
2. `task_id` 必须保留，用于后续连接 `/ws/output/{task_id}`。

**上传流程**
- 每个数据块以“JSON 元数据帧 + 二进制帧”方式发送 [`services/input-handler-python/main.py:114`](services/input-handler-python/main.py:114)。
- 元数据字段：`type`（`text` 或 `audio`）、`chunk_id`（从 0 递增）、`action` 固定为 `data_chunk`。前端当前实现与之对齐 [`front_end/src/composables/useApi.js:175`](front_end/src/composables/useApi.js:175)、[`front_end/src/composables/useApi.js:520`](front_end/src/composables/useApi.js:520)。
- 收到二进制帧后，服务端会回 `"File chunk received"` 文本确认 [`services/input-handler-python/main.py:138`](services/input-handler-python/main.py:138)，前端仅用于日志 [`front_end/src/composables/useApi.js:122`](front_end/src/composables/useApi.js:122)。
- 所有块发送完毕后，前端需发送 `{"action": "upload_complete"}` 通知 [`front_end/src/composables/useApi.js:190`](front_end/src/composables/useApi.js:190)。

**服务端响应**
- 队列入库完成后，input-handler 会发送 `{"type":"system","action":"upload_processed","status":"queued","task_id":...}` [`services/input-handler-python/main.py:176`](services/input-handler-python/main.py:176)。前端据此确认上传结束并断开输入通道 [`front_end/src/composables/useApi.js:114`](front_end/src/composables/useApi.js:114)。
- 若上传出错，会返回 `status: "error"`，并携带 `error` 字段 [`services/input-handler-python/main.py:189`](services/input-handler-python/main.py:189)。前端需展示错误并停止流程。

**错误与重连注意事项**
- 若 chunk 顺序不匹配，服务端会发送 `"Chunk ID mismatch"` 文本提示 [`services/input-handler-python/main.py:120`](services/input-handler-python/main.py:120)；前端当前直接中止 [`front_end/src/composables/useApi.js:125`](front_end/src/composables/useApi.js:125)。
- 连接关闭前未分配 `task_id` 时，应视为失败并提示用户 [`front_end/src/composables/useApi.js:150`](front_end/src/composables/useApi.js:150)。

## WebSocket `/ws/output/{task_id}`

**绑定逻辑**
- 连接时网关会校验 `task_id` 并反向代理到 output-handler [`services/output-handler-python/main.py:62`](services/output-handler-python/main.py:62)。task_id 必须为有效 UUID，否则会以 4004 关闭。
- 前端在获取到 task_id 后立刻发起连接，并在状态内保持单任务会话 [`front_end/src/composables/useApi.js:259`](front_end/src/composables/useApi.js:259)。

**主要消息类型**
1. **文本结果**：`{"status":"success","task_id":...,"content":...,"audio_present":bool}` [`services/output-handler-python/main.py:172`](services/output-handler-python/main.py:172)。若 `audio_present=false` 则任务结束，可关闭连接 [`front_end/src/composables/useApi.js:326`](front_end/src/composables/useApi.js:326)。
2. **音频流**：
   - 元数据帧 `{"type":"audio_chunk","task_id":...,"chunk_id":n,"total_chunks":m}` [`services/output-handler-python/main.py:216`](services/output-handler-python/main.py:216)。`total_chunks` 在流式场景可能为 `None` [`services/output-handler-python/main.py:245`](services/output-handler-python/main.py:245)。
   - 随后紧跟一个二进制帧（PCM/合成音频数据）。前端期望先收到元数据再处理二进制 [`front_end/src/composables/useApi.js:290`](front_end/src/composables/useApi.js:290)。
   - 全部发送完成后会收到 `{"type":"audio_complete","task_id":...}` [`services/output-handler-python/main.py:231`](services/output-handler-python/main.py:231)，前端在此时合并音频并断开连接 [`front_end/src/composables/useApi.js:348`](front_end/src/composables/useApi.js:348)。
3. **控制消息（可选）**：若启用流式同步链路，output-handler 可能下发 `{"type":"control","action":"STOP_ACK",...}` 等控制帧 [`services/output-handler-python/main.py:245`](services/output-handler-python/main.py:245)。前端应预留解析逻辑（目前尚未消费）。
4. **错误消息**：`{"status":"error","error":...}` 或 `{"type":"error",...}` 表示服务端处理失败 [`services/output-handler-python/main.py:238`](services/output-handler-python/main.py:238)。

**超时与清理**
- output-handler 会在 5 分钟超时后返回 `Processing timeout` 错误 [`services/output-handler-python/main.py:120`](services/output-handler-python/main.py:120)。前端需提示用户并允许重试。
- 连接关闭且未完成音频时，前端需要清理缓存并报告失败 [`front_end/src/composables/useApi.js:312`](front_end/src/composables/useApi.js:312)。

## 控制接口 `/control/stop`

- 请求：`POST /control/stop`，Body `{ "sessionId": "<task_id>" }` [`services/gateway-python/main.py:178`](services/gateway-python/main.py:178)。
- 成功：返回 output-handler 的响应（`{"ok": true}`）。
- 失败：
  - 400：缺少 `sessionId`。
  - 409：后端未启用 `SYNC_TTS_BARGE_IN`（打断功能关闭） [`services/output-handler-python/main.py:305`](services/output-handler-python/main.py:305)。
  - 503：output-handler 尚未连接上游对话引擎。
  - 5xx / 502：网络或代理异常。
- 前端若新增“停止播放/打断”按钮，应发送当前任务 ID（即 task_id），并在收到 409/503 时给出清晰提示。

## 诊断接口

- `GET /health`：返回网关运行状态、后端地址与活跃连接数 [`services/gateway-python/main.py:268`](services/gateway-python/main.py:268)。
- `GET /connections`：列出当前活跃的代理连接 ID [`services/gateway-python/main.py:278`](services/gateway-python/main.py:278)。
- `GET /internal/output/health`：代理 output-handler `/health`，可用于前端或管理界面展示 TTS 服务状态 [`services/gateway-python/main.py:210`](services/gateway-python/main.py:210)。

## ASR 任务投递 `/api/asr`

- 请求体：`{"path": "/绝对路径.wav", "options": {"lang": "zh", "timestamps": true}}` [`services/gateway-python/src/services/asr_routes.py:33`](services/gateway-python/src/services/asr_routes.py:33)。
- 响应：`{"task_id": "..."}`。
- 该接口主要面向后端工具或运维脚本；当前前端未直接使用。但如需提供“上传本地文件执行转写”功能，可直接复用。

## 集成注意事项

- 网关通过环境变量 `INPUT_HANDLER_URL`、`OUTPUT_HANDLER_URL` 指向后端服务，默认分别为 `ws://localhost:8001`、`ws://localhost:8002` [`services/gateway-python/main.py:24`](services/gateway-python/main.py:24)。
- Input-handler 的同步链路仅当 `ENABLE_SYNC_CORE=true` 时会直接推送至 dialog-engine；否则所有任务都会入 Redis 队列等待后续处理 [`services/input-handler-python/main.py:183`](services/input-handler-python/main.py:183)。
- Output-handler 的流式 TTS (`/ws/ingest/tts`) 与打断功能由 `SYNC_TTS_STREAMING`、`SYNC_TTS_BARGE_IN` 控制，默认关闭 [`services/output-handler-python/main.py:300`](services/output-handler-python/main.py:300)。前端应在功能不可用时隐藏或禁用相关按钮。
- 前端当前所有 WebSocket URL 均以浏览器 `window.location.hostname` 拼接端口 8000 生成 [`front_end/src/composables/useApi.js:6`](front_end/src/composables/useApi.js:6)。重构时可改为配置化但需保持路径不变或同步更新后端。
- 处理流程：输入 > 分配 task_id > 入队处理 > output-handler 通过 Redis Pub/Sub 推送结果 [`services/output-handler-python/main.py:103`](services/output-handler-python/main.py:103)。前端需确保在收到 `upload_processed` 前不要断开输入连接，以免任务丢失。

以上契约均依据当前代码实现提取，如需调整协议，请同步修改相关服务并更新本文档。

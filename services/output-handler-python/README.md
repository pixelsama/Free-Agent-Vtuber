# AIVtuber Output Handler

专门负责向前端推送AI处理结果的WebSocket服务模块，基于事件驱动架构设计。

## 功能特性

- **纯输出处理**: 专注于推送AI处理结果给前端，不处理输入
- **Redis订阅**: 监听特定任务的响应频道 `task_response:{task_id}`
- **音频分块传输**: 支持大音频文件的分块传输
- **任务状态跟踪**: 实时跟踪连接和处理状态
- **超时处理**: 5分钟处理超时保护
- **健康检查**: 提供服务状态监控端点

## 接口端点

### 输出WebSocket
- **端点**: `ws://localhost:8001/ws/output/{task_id}`
- **功能**: 向前端推送AI处理结果(文本+音频)
- **流程**: 连接 → 验证task_id → 订阅Redis频道 → 推送结果

### HTTP端点
- **状态查询**: `GET /status/{task_id}` - 查询任务状态
- **健康检查**: `GET /health` - 服务健康状态
- **主页**: `GET /` - 服务信息页面

## 工作流程

1. **客户端连接** → WebSocket `/ws/output/{task_id}`
2. **验证任务ID** → 检查UUID格式有效性
3. **订阅Redis频道** → 监听 `task_response:{task_id}`
4. **等待AI结果** → 5分钟超时保护
5. **推送文本响应** → JSON格式返回文本内容
6. **音频分块传输** → 64KB分块传输音频文件
7. **完成信号** → 发送传输完成标志

## 安装和运行

1. **安装依赖**
```bash
cd services/output-handler-python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **启动Redis**
```bash
redis-server
```

3. **运行模块**
```bash
python main.py
```

服务将启动在 `http://localhost:8001`

## Redis集成

### 响应频道订阅
- **频道名**: `task_response:{task_id}`
- **消息格式**:
```json
{
    "text": "AI回复的文本内容",
    "audio_file": "/tmp/aivtuber_tasks/{task_id}/output.wav"
}
```

## 响应消息格式

### 成功响应（仅文本）
```json
{
    "status": "success",
    "task_id": "uuid-string",
    "content": "AI回复的文本内容",
    "audio_present": false
}
```

### 成功响应（包含音频）
```json
{
    "status": "success",
    "task_id": "uuid-string", 
    "content": "AI回复的文本内容",
    "audio_present": true
}
```

### 音频块元数据
```json
{
    "type": "audio_chunk",
    "task_id": "uuid-string",
    "chunk_id": 0,
    "total_chunks": 5
}
```

### 音频完成信号
```json
{
    "type": "audio_complete",
    "task_id": "uuid-string"
}
```

### 错误响应
```json
{
    "status": "error",
    "error": "错误描述信息"
}
```

## 配置

主要配置在 `config.json` 中：

- WebSocket输出端点设置
- 音频分块大小配置
- Redis连接参数
- 服务器端口设置

## 错误处理

- **连接错误**: task_id格式验证，连接超时
- **Redis错误**: 频道订阅失败，消息解析错误
- **文件错误**: 音频文件不存在，读取失败
- **传输错误**: WebSocket断开，数据传输失败

## 与其他模块集成

此模块作为整个AIVtuber系统的输出网关：

1. 监听Redis响应频道
2. 接收AI处理模块的结果
3. 向前端推送文本和音频响应
4. 提供任务状态查询接口

AI处理模块可以通过 `task_response:{task_id}` 频道发布处理结果。

## 服务监控

- **活跃连接数**: 实时显示当前WebSocket连接数
- **任务状态**: 跟踪每个任务的处理状态
- **Redis连接**: 监控Redis连接健康状态
- **错误日志**: 详细的错误记录和调试信息

## 文件结构

```
output-handler-python/
├── main.py              # 主程序
├── requirements.txt     # 依赖包
├── config.json         # 配置文件
└── README.md           # 说明文档
```
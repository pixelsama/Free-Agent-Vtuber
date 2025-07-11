# AIVtuber AI Chat Processor

AI聊天处理模块，负责处理用户输入并生成智能回复。基于事件驱动架构，通过Redis与其他模块通信。

## 功能特性

- **Redis队列监听**: 监听 `user_input_queue` 队列获取用户输入
- **智能文本处理**: 基于规则的简单AI回复（可扩展为真实AI模型）
- **音频处理支持**: 预留音频识别和TTS接口
- **异步处理**: 支持并发处理多个任务
- **响应发布**: 通过Redis频道发送处理结果
- **错误处理**: 完善的错误处理和日志记录

## 工作流程

1. **监听队列** → 持续监听 `user_input_queue` 队列
2. **接收任务** → 获取包含用户输入的任务数据
3. **处理输入** → 根据类型（文本/音频）进行相应处理
4. **生成回复** → 调用AI逻辑生成智能回复
5. **发布结果** → 通过 `task_response:{task_id}` 频道发送结果

## 安装和运行

1. **安装依赖**
```bash
cd services/chat-ai-python
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

## Redis集成

### 输入队列监听
- **队列名**: `user_input_queue`
- **消息格式**:
```json
{
    "task_id": "uuid-string",
    "type": "text|audio",
    "input_file": "/tmp/aivtuber_tasks/{task_id}/input.txt",
    "timestamp": 1641234567.89
}
```

### 响应发布
- **频道名**: `task_response:{task_id}`
- **响应格式**:
```json
{
    "text": "AI回复的文本内容",
    "audio_file": "/path/to/output.wav"  // 可选
}
```

## AI处理逻辑

### 当前实现（简单规则）
- 问候语识别和回复
- 关键词匹配和响应
- 问题类型判断
- 默认友好回复

### 扩展接口
```python
async def process_text(self, text: str) -> str:
    # 这里可以集成：
    # - OpenAI GPT API
    # - Claude API
    # - 本地大语言模型
    # - 其他AI服务
    pass
```

## 音频处理

### 语音识别（预留）
```python
async def process_audio(self, audio_file: str) -> tuple[str, Optional[str]]:
    # 可以集成：
    # - Whisper
    # - Azure Speech Services
    # - Google Speech-to-Text
    pass
```

### 语音合成（预留）
```python
async def generate_speech(self, text: str) -> str:
    # 可以集成：
    # - Edge TTS
    # - ElevenLabs
    # - Azure TTS
    pass
```

## 配置

主要配置在 `config.json` 中：

- Redis连接参数
- AI模型设置
- 处理并发限制
- 日志级别配置

## 错误处理

- **Redis连接错误**: 自动重连机制
- **任务处理错误**: 错误响应发送
- **文件读取错误**: 优雅降级
- **AI处理超时**: 超时保护

## 性能监控

- **处理中任务**: `processing_tasks` 字典跟踪
- **任务状态**: processing, completed, error
- **日志记录**: 详细的处理日志

## 扩展建议

### 真实AI集成
1. 安装AI SDK（如 `openai`）
2. 在 `process_text` 方法中调用API
3. 添加API密钥配置
4. 实现重试和错误处理

### 语音功能
1. 集成Whisper进行语音识别
2. 集成TTS引擎生成语音回复
3. 音频文件格式转换
4. 音频质量优化

### 高级功能
1. 对话上下文记忆
2. 用户偏好学习
3. 情感分析和表达
4. 多轮对话管理

## 文件结构

```
chat-ai-python/
├── main.py              # 主程序
├── requirements.txt     # 依赖包
├── config.json         # 配置文件
└── README.md           # 说明文档
```

## 与其他模块协作

1. **输入模块** → 发送任务到 `user_input_queue`
2. **AI模块** → 处理任务，发送结果到响应频道
3. **输出模块** → 监听响应频道，推送给前端

这样形成完整的输入→处理→输出的事件驱动流程。
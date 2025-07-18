# TTS模块设计文档

## 概述

TTS模块是AIVtuber项目中负责文本转语音功能的核心组件。该模块采用可插拔的提供商架构，支持多种TTS服务，并通过Redis消息总线与其他系统组件进行通信。模块遵循项目的事件驱动架构原则，提供异步、高性能的语音合成服务。

## 架构

### 整体架构图

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Redis消息总线  │◄──►│   TTS主服务模块   │◄──►│  TTS提供商工厂   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                         │
                              ▼                         ▼
                       ┌──────────────┐         ┌─────────────────┐
                       │   配置管理    │         │  提供商实现层    │
                       └──────────────┘         │  ├─OpenAI TTS   │
                                                │  ├─Edge TTS     │
                                                │  ├─ElevenLabs   │
                                                │  └─自定义提供商  │
                                                └─────────────────┘
```

### 模块结构

```
services/tts-python/
├── main.py                 # 主入口文件
├── config.json            # 配置文件
├── requirements.txt       # 依赖文件
├── tts_service.py         # TTS服务主类
├── config_manager.py      # 配置管理器
├── providers/             # TTS提供商实现
│   ├── __init__.py
│   ├── tts_provider.py    # 抽象基类
│   ├── openai_tts.py      # OpenAI TTS实现
│   ├── edge_tts.py        # Edge TTS实现
│   └── elevenlabs_tts.py  # ElevenLabs TTS实现
└── utils/
    ├── __init__.py
    ├── logger.py          # 日志工具
    └── redis_client.py    # Redis客户端封装
```

## 组件和接口

### 1. TTS服务主类 (TTSService)

**职责：**
- 管理Redis连接和消息处理
- 协调TTS提供商的调用
- 处理错误和异常情况
- 提供服务生命周期管理

**主要接口：**
```python
class TTSService:
    async def start(self) -> None
    async def stop(self) -> None
    async def process_tts_request(self, message: dict) -> None
    async def handle_error(self, error: Exception, context: dict) -> None
```

### 2. TTS提供商抽象基类 (TTSProvider)

**职责：**
- 定义统一的TTS提供商接口
- 提供基础的参数验证和错误处理

**接口定义：**
```python
from abc import ABC, abstractmethod

class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, **kwargs) -> bytes
    
    @abstractmethod
    def validate_config(self, config: dict) -> bool
    
    def get_supported_voices(self) -> List[str]
    def get_supported_models(self) -> List[str]
```

### 3. 提供商工厂 (ProviderFactory)

**职责：**
- 根据配置创建相应的TTS提供商实例
- 管理提供商的注册和发现

**接口：**
```python
class ProviderFactory:
    @staticmethod
    def create_provider(provider_name: str, config: dict) -> TTSProvider
    
    @staticmethod
    def register_provider(name: str, provider_class: type) -> None
    
    @staticmethod
    def get_available_providers() -> List[str]
```

### 4. 配置管理器 (ConfigManager)

**职责：**
- 加载和验证配置文件
- 提供配置热重载功能
- 管理环境变量覆盖

**接口：**
```python
class ConfigManager:
    def load_config(self, config_path: str) -> dict
    def validate_config(self, config: dict) -> bool
    def get_provider_config(self, provider_name: str) -> dict
    def reload_config(self) -> None
```

## 数据模型

### TTS请求消息格式

```json
{
    "message_id": "uuid-string",
    "timestamp": "2024-01-01T12:00:00Z",
    "text": "要转换的文本内容",
    "provider": "openai",  // 可选，覆盖默认提供商
    "voice_params": {      // 可选，覆盖默认参数
        "voice": "alloy",
        "model": "tts-1",
        "speed": 1.0
    },
    "response_channel": "tts_audio_output"  // 可选，指定响应频道
}
```

### TTS响应消息格式

```json
{
    "message_id": "uuid-string",
    "timestamp": "2024-01-01T12:00:01Z",
    "status": "success",
    "audio_data": "base64-encoded-audio-bytes",
    "metadata": {
        "provider": "openai",
        "voice": "alloy",
        "model": "tts-1",
        "text_length": 25,
        "audio_duration": 3.2,
        "processing_time": 0.8
    }
}
```

### 错误响应消息格式

```json
{
    "message_id": "uuid-string",
    "timestamp": "2024-01-01T12:00:01Z",
    "status": "error",
    "error": {
        "code": "TTS_SYNTHESIS_FAILED",
        "message": "Failed to synthesize audio",
        "details": "API rate limit exceeded",
        "provider": "openai"
    }
}
```

## 错误处理

### 错误分类

1. **配置错误**
   - 无效的API密钥
   - 不支持的提供商
   - 配置文件格式错误

2. **网络错误**
   - API请求超时
   - 网络连接失败
   - 服务不可用

3. **业务逻辑错误**
   - 文本内容过长
   - 不支持的语音参数
   - 配额超限

### 错误处理策略

1. **重试机制**
   - 网络错误：指数退避重试，最多3次
   - 临时性错误：短暂延迟后重试
   - 永久性错误：立即失败

2. **降级策略**
   - 主提供商失败时自动切换到备用提供商
   - 参数不支持时使用默认参数
   - 服务不可用时返回错误消息

3. **错误上报**
   - 所有错误记录到日志
   - 关键错误发送到错误处理频道
   - 提供详细的错误上下文信息

## 测试策略

### 单元测试

1. **提供商测试**
   - 测试各个TTS提供商的基本功能
   - 模拟API响应进行测试
   - 验证参数验证逻辑

2. **配置管理测试**
   - 测试配置文件加载和验证
   - 测试环境变量覆盖
   - 测试配置热重载

3. **错误处理测试**
   - 测试各种错误场景
   - 验证重试机制
   - 测试降级策略

### 集成测试

1. **Redis通信测试**
   - 测试消息接收和发送
   - 验证消息格式正确性
   - 测试并发处理能力

2. **端到端测试**
   - 测试完整的TTS流程
   - 验证与其他模块的集成
   - 测试实际的TTS API调用

### 性能测试

1. **并发处理测试**
   - 测试同时处理多个TTS请求
   - 验证异步处理性能
   - 测试资源使用情况

2. **压力测试**
   - 测试高负载下的系统表现
   - 验证错误处理的稳定性
   - 测试内存和CPU使用

## 配置示例

### 完整配置文件示例

```json
{
    "redis": {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "password": null
    },
    "tts": {
        "default_provider": "openai",
        "request_queue": "tts_requests",
        "response_channel": "tts_responses",
        "error_channel": "tts_errors",
        "max_text_length": 4000,
        "timeout": 30,
        "retry_attempts": 3,
        "retry_delay": 1.0
    },
    "providers": {
        "openai": {
            "api_key": "${OPENAI_API_KEY}",
            "model": "tts-1",
            "voice": "alloy",
            "speed": 1.0,
            "response_format": "mp3"
        },
        "edge": {
            "voice": "zh-CN-XiaoxiaoNeural",
            "rate": "+0%",
            "pitch": "+0Hz"
        },
        "elevenlabs": {
            "api_key": "${ELEVENLABS_API_KEY}",
            "voice_id": "21m00Tcm4TlvDq8ikWAM",
            "model_id": "eleven_monolingual_v1",
            "stability": 0.5,
            "similarity_boost": 0.5
        }
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "tts_service.log"
    }
}
```

## 部署考虑

### 依赖管理

- 使用独立的虚拟环境
- 明确指定依赖版本
- 支持可选依赖（如特定提供商的SDK）

### 环境变量

- API密钥通过环境变量管理
- 支持配置文件中的变量替换
- 提供默认值和验证

### 监控和日志

- 结构化日志输出
- 关键指标监控（处理时间、成功率等）
- 健康检查接口

### 扩展性考虑

- 提供商插件化架构
- 支持动态加载新提供商
- 配置热重载支持
- 水平扩展能力（多实例部署）
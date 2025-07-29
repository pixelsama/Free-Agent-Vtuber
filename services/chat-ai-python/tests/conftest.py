import json
import os
import sys
import pytest
import redis.asyncio as redis
from unittest.mock import AsyncMock, Mock
from pathlib import Path
# 直接导入，因为chat_ai_python是当前工作目录
from main import AIProcessor, TaskProcessor, load_config


@pytest.fixture
def sample_config():
    """提供示例配置"""
    return {
        "ai": {
            "provider": "openai_compatible",
            "api_base": "https://test-api.example.com/v1",
            "api_key": "test-key",
            "model": "test-model",
            "max_tokens": 100,
            "temperature": 0.7,
            "timeout": 30,
            "max_retries": 3,
            "system_prompt": "你是一个测试AI助手",
            "fallback_to_rules": True
        },
        "redis": {
            "host": "localhost",
            "port": 6379
        },
        "processing": {
            "max_concurrent_tasks": 10,
            "task_timeout": 60,
            "response_delay": 0.1
        }
    }


@pytest.fixture
def mock_redis():
    """提供模拟的Redis客户端"""
    mock_redis = AsyncMock(spec=redis.Redis)
    mock_redis.ping = AsyncMock(return_value=True)
    mock_redis.publish = AsyncMock(return_value=None)
    mock_redis.lpush = AsyncMock(return_value=None)
    mock_redis.lrange = AsyncMock(return_value=[])
    return mock_redis


@pytest.fixture
def mock_ai_client():
    """提供模拟的AI客户端"""
    mock_client = AsyncMock()
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "这是模拟的AI回复"
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def ai_processor(sample_config):
    """提供AI处理器实例"""
    # 保存原始配置
    import main as main_module
    original_config = main_module.config.copy() if main_module.config else {}
    
    # 设置测试配置
    main_module.config = sample_config
    
    # 创建处理器
    processor = AIProcessor()
    
    # 恢复原始配置
    yield processor
    
    main_module.config = original_config


@pytest.fixture
def task_processor(sample_config):
    """提供任务处理器实例"""
    # 保存原始配置
    import main as main_module
    original_config = main_module.config.copy() if main_module.config else {}
    
    # 设置测试配置
    main_module.config = sample_config
    
    # 创建处理器
    processor = TaskProcessor()
    
    # 恢复原始配置
    yield processor
    
    main_module.config = original_config
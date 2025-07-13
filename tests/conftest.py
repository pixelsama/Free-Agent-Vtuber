"""
pytest配置文件
包含测试fixtures和通用配置
"""

import pytest
import asyncio
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 移除event_loop fixture，使用默认的
# @pytest.fixture(scope="session")
# def event_loop():
#     """创建事件循环用于异步测试"""
#     loop = asyncio.new_event_loop()
#     yield loop
#     loop.close()

@pytest.fixture
def sample_config():
    """标准测试配置"""
    return {
        "memory": {
            "max_memory_size": 100,
            "memory_ttl_hours": 24,
            "context_window": 20,
            "enable_global_context": True,
            "global_memory_limit": 1000,
            "cleanup_hours": 48
        },
        "redis": {
            "host": "localhost",
            "port": 6379,
            "decode_responses": True
        }
    }

@pytest.fixture
def sample_user_message():
    """样例用户消息"""
    return {
        "message_id": "test_msg_001",
        "user_id": "test_user_123",
        "type": "text",
        "content": "这是一条测试消息",
        "source": "user",
        "require_ai_response": True,
        "metadata": {
            "task_id": "task_001",
            "priority": "normal"
        }
    }

@pytest.fixture
def sample_ai_message():
    """样例AI回复消息"""
    return {
        "message_id": "test_ai_001",
        "user_id": "test_user_123", 
        "type": "text",
        "content": "这是AI的回复",
        "source": "ai",
        "require_ai_response": False,
        "metadata": {
            "model": "test-model",
            "response_time": 0.5
        }
    }

# pytest标记配置
pytest_plugins = []

def pytest_configure(config):
    """pytest配置"""
    config.addinivalue_line(
        "markers", "unit: 单元测试标记"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试标记"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试标记"
    )
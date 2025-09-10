"""
测试配置和fixture定义
"""
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
import sys

import pytest

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.models.memory import MemoryCategory, MemoryMetadata, UserMemory, UserProfile
from src.models.messages import MemoryUpdateMessage, LTMRequest, LTMResponse


@pytest.fixture
def test_config():
    """测试配置"""
    return {
        "redis": {
            "host": "localhost",
            "port": 6379,
            "db": 1  # 使用测试数据库
        },
        "qdrant": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "test_mem0_collection"
        },
        "mem0": {
            "config_path": "config/mem0_config.yaml"
        },
        "channels": {
            "memory_updates": "memory_updates",
            "ltm_responses": "ltm_responses"
        },
        "queues": {
            "ltm_requests": "ltm_requests"
        }
    }


@pytest.fixture
def mock_redis():
    """Mock Redis客户端"""
    from unittest.mock import Mock, AsyncMock
    
    mock = AsyncMock()
    mock.get.return_value = None
    mock.setex.return_value = True
    mock.publish.return_value = 1
    mock.lpush.return_value = 1
    mock.brpop.return_value = None
    
    # Mock pubsub behavior
    from unittest.mock import Mock
    mock_pubsub_instance = Mock()
    mock_pubsub_instance.subscribe = AsyncMock()
    mock_pubsub_instance.unsubscribe = AsyncMock()
    mock_pubsub_instance.close = AsyncMock()
    # listen()应该返回一个可以被async for迭代的对象
    mock_pubsub_instance.listen = Mock()
    
    # pubsub()是同步方法，使用Mock而不是AsyncMock
    mock.pubsub = Mock(return_value=mock_pubsub_instance)
    return mock


@pytest.fixture
def mock_mem0():
    """Mock Mem0客户端"""
    mock = AsyncMock()
    mock.add.return_value = "memory_123"
    mock.search.return_value = []
    mock.get.return_value = None
    mock.update.return_value = True
    return mock


@pytest.fixture
def mock_qdrant():
    """Mock Qdrant客户端"""
    mock = AsyncMock()
    mock.search.return_value = []
    mock.upsert.return_value = True
    mock.count.return_value = {"count": 0}
    return mock


@pytest.fixture
def sample_memory_metadata():
    """示例记忆元数据"""
    return MemoryMetadata(
        category=MemoryCategory.PREFERENCE,
        confidence=0.8,
        source="conversation",
        tags=["动漫", "娱乐"],
        created_at=datetime.now()
    )


@pytest.fixture
def sample_user_memory(sample_memory_metadata):
    """示例用户记忆"""
    return UserMemory(
        user_id="test_user_001",
        content="用户喜欢看动漫，特别是《进击的巨人》",
        metadata=sample_memory_metadata
    )


@pytest.fixture
def sample_user_profile():
    """示例用户画像"""
    return UserProfile(
        user_id="test_user_001",
        preferences=["动漫", "音乐"],
        personality_traits=["活泼", "友善"],
        habits=["晚上聊天", "喜欢分享"],
        important_events=["2024年生日"],
        memory_count=5,
        last_updated=datetime.now()
    )


@pytest.fixture
def sample_memory_update_message():
    """示例memory_updates消息"""
    return MemoryUpdateMessage(
        user_id="test_user_001",
        content="我最喜欢的动漫是《进击的巨人》",
        source="conversation",
        timestamp=1234567890,
        meta={"session_id": "session_001"}
    )


@pytest.fixture
def sample_ltm_request():
    """示例LTM请求"""
    return LTMRequest(
        request_id="req_1234567890",
        type="search",
        user_id="test_user_001",
        data={
            "query": "用户喜欢什么动漫",
            "limit": 5
        }
    )


"""
TDD循环1: Redis消息总线基础架构测试
"""
import asyncio
import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from src.core.redis_client import RedisMessageBus
from src.models.messages import MemoryUpdateMessage, LTMRequest, LTMResponse


class TestRedisMessageBus:
    """测试Redis消息总线功能"""

    @pytest.fixture
    def message_bus(self, mock_redis, test_config):
        """创建消息总线实例"""
        bus = RedisMessageBus(test_config["redis"])
        bus.redis_client = mock_redis
        bus.pubsub_client = mock_redis
        return bus

    @pytest.mark.asyncio
    async def test_consume_memory_updates_message(self, message_bus):
        """测试消费memory_updates频道消息"""
        # Arrange
        message_data = {
            "user_id": "test_user",
            "content": "用户喜欢动漫", 
            "source": "conversation",
            "timestamp": 1234567890,
            "meta": {"session_id": "session_001"}
        }
        
        # Mock listen方法返回async generator
        messages = [
            {"type": "subscribe", "channel": "memory_updates"},
            {"type": "message", "data": json.dumps(message_data)}
        ]
        
        async def mock_listen():
            for msg in messages:
                yield msg
        
        # 获取mock pubsub实例并设置listen的返回值
        mock_pubsub = message_bus.pubsub_client.pubsub.return_value
        # listen()应该直接返回async generator，不是coroutine
        mock_pubsub.listen.return_value = mock_listen()
        
        # Act
        processed_messages = []
        async def message_handler(message: MemoryUpdateMessage):
            processed_messages.append(message)
            message_bus._running = False  # 处理完第一条消息后停止
        
        # 启动订阅（应该处理一条消息后停止）
        await message_bus.subscribe_memory_updates(message_handler)
        
        # Assert
        assert len(processed_messages) == 1
        assert processed_messages[0].user_id == "test_user"
        assert processed_messages[0].content == "用户喜欢动漫"
        
        # 验证Redis方法被正确调用
        message_bus.pubsub_client.pubsub.assert_called_once()
        mock_pubsub.subscribe.assert_called_once_with("memory_updates")
        mock_pubsub.unsubscribe.assert_called_once()
        mock_pubsub.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_ltm_requests(self, message_bus):
        """测试处理ltm_requests队列消息"""
        # Arrange
        request_data = {
            "request_id": "req_1234567890", 
            "type": "search",
            "user_id": "test_user",
            "data": {
                "query": "动漫",
                "limit": 5
            }
        }
        
        # 模拟队列返回消息，然后返回None表示队列空了
        message_bus.redis_client.brpop.side_effect = [
            ("ltm_requests", json.dumps(request_data)),
            None  # 第二次调用返回None，停止循环
        ]
        
        message_bus.redis_client.publish = AsyncMock()
        
        # Act
        processed_requests = []
        async def request_handler(request: LTMRequest):
            processed_requests.append(request)
            message_bus._running = False  # 处理完第一个请求后停止
            return LTMResponse(
                request_id=request.request_id,
                user_id=request.user_id,
                memories=[{"content": "用户喜欢动漫", "score": 0.9}]
            )
        
        await message_bus.process_ltm_requests(request_handler)
        
        # Assert
        assert len(processed_requests) == 1
        assert processed_requests[0].request_id == "req_1234567890"
        assert processed_requests[0].type == "search"
        
        # 验证响应被发布
        message_bus.redis_client.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_ltm_response(self, message_bus):
        """测试发布ltm_responses消息"""
        # Arrange
        response = LTMResponse(
            request_id="req_1234567890",
            user_id="test_user",
            success=True,
            memories=[{"content": "用户喜欢动漫", "score": 0.9}]
        )
        
        # Act
        await message_bus.publish_ltm_response(response)
        
        # Assert
        message_bus.redis_client.publish.assert_called_once()
        call_args = message_bus.redis_client.publish.call_args
        assert call_args[0][0] == "ltm_responses"
        
        published_data = json.loads(call_args[0][1])
        assert published_data["request_id"] == "req_1234567890"
        assert published_data["user_id"] == "test_user"

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, test_config):
        """测试Redis连接失败的情况"""
        # Arrange
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("连接失败")
        
        # Act & Assert
        message_bus = RedisMessageBus(test_config["redis"])
        message_bus.redis_client = mock_redis
        
        with pytest.raises(Exception) as exc_info:
            await message_bus.check_connection()
        
        assert "连接失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_message_serialization_error(self, message_bus):
        """测试消息序列化错误处理"""
        # Arrange
        invalid_response = LTMResponse(
            request_id="req_123",
            user_id="test_user",
            success=True
        )
        
        # Mock序列化失败
        from src.core.redis_client import MessageSerializationError
        with pytest.raises(MessageSerializationError):
            # 模拟无法序列化的对象
            invalid_response.memories = [{"invalid": object()}]
            await message_bus.publish_ltm_response(invalid_response)

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, message_bus):
        """测试并发消息处理"""
        # Arrange
        messages = []
        for i in range(10):
            messages.append(MemoryUpdateMessage(
                user_id=f"user_{i}",
                content=f"消息{i}",
                source="conversation",
                timestamp=1234567890 + i
            ))
        
        processed_count = 0
        async def message_handler(message: MemoryUpdateMessage):
            nonlocal processed_count
            await asyncio.sleep(0.01)  # 模拟处理时间
            processed_count += 1
        
        # Act
        tasks = []
        for message in messages:
            tasks.append(message_handler(message))
        
        await asyncio.gather(*tasks)
        
        # Assert
        assert processed_count == 10

    @pytest.mark.asyncio
    async def test_redis_config_from_dict(self, test_config):
        """测试RedisConfig从字典创建"""
        from src.core.redis_client import RedisConfig
        
        config = RedisConfig.from_dict(test_config["redis"])
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 1

    @pytest.mark.asyncio
    async def test_message_serialization_methods(self, message_bus, sample_memory_update_message, sample_ltm_request):
        """测试消息序列化/反序列化方法"""
        # 测试memory update消息
        serialized = json.dumps(sample_memory_update_message.model_dump())
        deserialized = message_bus._deserialize_memory_update(serialized)
        assert deserialized.user_id == sample_memory_update_message.user_id
        
        # 测试LTM request消息
        serialized = json.dumps(sample_ltm_request.model_dump())
        deserialized = message_bus._deserialize_ltm_request(serialized)
        assert deserialized.request_id == sample_ltm_request.request_id
        
        # 测试LTM response消息
        response = LTMResponse(
            request_id="test_123",
            user_id="test_user",
            success=True,
            memories=[{"content": "test", "score": 0.9}]
        )
        serialized = message_bus._serialize_ltm_response(response)
        # 验证可以反序列化
        parsed = json.loads(serialized)
        assert parsed["request_id"] == "test_123"
"""
TDD循环1: Redis消息总线基础架构测试
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock

from src.core.redis_client import RedisMessageBus
from src.models.messages import MemoryUpdateMessage, LTMRequest, LTMResponse


class TestRedisMessageBus:
    """测试Redis消息总线功能"""

    @pytest.fixture
    async def message_bus(self, mock_redis, test_config):
        """创建消息总线实例"""
        bus = RedisMessageBus(test_config["redis"])
        bus.redis_client = mock_redis
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
        
        # 模拟订阅接收消息
        message_bus.redis_client.subscribe.return_value = AsyncMock()
        mock_message = AsyncMock()
        mock_message.decode.return_value = json.dumps(message_data)
        
        # Act
        processed_messages = []
        async def message_handler(message: MemoryUpdateMessage):
            processed_messages.append(message)
        
        await message_bus.subscribe_memory_updates(message_handler)
        
        # 模拟接收到消息
        await message_handler(MemoryUpdateMessage(**message_data))
        
        # Assert
        assert len(processed_messages) == 1
        assert processed_messages[0].user_id == "test_user"
        assert processed_messages[0].content == "用户喜欢动漫"

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
        
        # 模拟队列返回消息
        message_bus.redis_client.brpop.return_value = (
            "ltm_requests",
            json.dumps(request_data)
        )
        
        # Act
        processed_requests = []
        async def request_handler(request: LTMRequest):
            processed_requests.append(request)
            # 返回模拟响应
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
        with pytest.raises((TypeError, ValueError)):
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
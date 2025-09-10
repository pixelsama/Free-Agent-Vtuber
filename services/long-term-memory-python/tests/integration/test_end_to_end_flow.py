"""
TDD循环6：端到端数据流集成测试

测试目标：
1. 完整的记忆数据流 - 从memory_updates到Mem0存储
2. 跨服务消息传递验证
3. 数据持久化和检索流程
4. 系统集成的稳定性
"""
import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio

from src.core.redis_client import RedisMessageBus
from src.core.mem0_client import Mem0Service
from src.services.message_processor import MessageProcessor
from src.services.memory_service import MemoryService


@pytest.fixture
def mock_redis_client():
    """模拟Redis客户端"""
    client = AsyncMock()
    # 配置publish方法
    client.publish.return_value = True
    # 配置订阅方法
    client.subscribe.return_value = AsyncMock()
    return client


@pytest.fixture  
def mock_mem0_client():
    """模拟Mem0客户端"""
    client = AsyncMock()
    # 配置add方法返回内存ID
    client.add.return_value = "mem_001"
    # 配置search方法返回相关记忆
    client.search.return_value = [
        {
            "id": "mem_001",
            "memory": "用户说他喜欢《进击的巨人》这部动漫",
            "metadata": {"category": "preference", "confidence": 0.9}
        }
    ]
    return client


@pytest.fixture
def message_processor(mock_redis_client, mock_mem0_client):
    """消息处理器实例"""
    return MessageProcessor(mock_redis_client, mock_mem0_client)


@pytest.fixture
def memory_service(mock_mem0_client, mock_redis_client):
    """记忆服务实例"""
    return MemoryService(mock_mem0_client, mock_redis_client)


class TestEndToEndFlow:
    """端到端数据流集成测试"""

    async def test_complete_memory_flow(self, message_processor, mock_redis_client, mock_mem0_client):
        """测试完整的记忆数据流 - TDD循环6核心测试"""
        # 模拟从memory-python发来的memory_updates消息
        memory_update = {
            "user_id": "test_user",
            "content": "用户说他喜欢《进击的巨人》这部动漫",
            "source": "conversation",
            "timestamp": 1234567890,
            "meta": {"session_id": "session_001"}
        }
        
        # 测试消息处理
        result = await message_processor.process_memory_update(memory_update)

        # 验证处理结果包含具体字段
        assert result is not None
        assert result.get("memory_id") == "mem_001"
        assert result.get("status") == "success"
        
        # 验证Mem0存储被调用
        mock_mem0_client.add.assert_called_once()
        call_args = mock_mem0_client.add.call_args[1]
        assert call_args["messages"] == memory_update["content"]
        assert call_args["user_id"] == "test_user"

    async def test_memory_updates_subscription_flow(self, message_processor, mock_redis_client, mock_mem0_client):
        """测试memory_updates订阅处理流程"""
        test_message = {
            "user_id": "test_user",
            "content": "用户喜欢编程，特别是Python开发",
            "source": "conversation",
            "timestamp": int(datetime.now().timestamp())
        }

        # 配置mock的订阅消息生成器
        async def message_generator():
            yield {"type": "message", "data": json.dumps(test_message)}

        mock_channel = AsyncMock()
        mock_channel.listen = MagicMock(return_value=message_generator())
        mock_redis_client.pubsub.return_value = mock_channel

        # 启动订阅处理
        await message_processor.start_memory_updates_subscription()

        # 验证订阅和消息处理
        mock_redis_client.pubsub.assert_called_once()
        assert mock_mem0_client.add.call_count == 1

    async def test_cross_service_data_flow(self, memory_service, mock_mem0_client):
        """测试跨服务数据流转"""
        user_id = "test_user"
        memory_content = "用户是软件工程师，喜欢开源项目"
        
        # 存储记忆
        memory_id = await memory_service.store_memory(
            user_id=user_id,
            content=memory_content,
            metadata={"source": "conversation"}
        )
        
        # 验证存储成功
        assert memory_id == "mem_001"
        
        # 搜索相关记忆
        related_memories = await memory_service.search_related_memories(
            user_id=user_id,
            query="软件工程师",
            limit=5
        )

        # 验证搜索结果包含预期记忆
        assert len(related_memories) > 0
        assert related_memories[0]["id"] == "mem_001"

    async def test_data_persistence_and_retrieval(self, memory_service, mock_mem0_client):
        """测试数据持久化和检索流程"""
        user_id = "test_user"
        
        # 存储多条记忆
        memories_to_store = [
            {"content": "用户喜欢看动漫", "category": "preference"},
            {"content": "用户是程序员", "category": "profession"},
            {"content": "用户性格内向", "category": "personality"}
        ]
        
        stored_ids = []
        for memory_data in memories_to_store:
            memory_id = await memory_service.store_memory(
                user_id=user_id,
                content=memory_data["content"],
                metadata={"category": memory_data["category"]}
            )
            stored_ids.append(memory_id)
        
        # 验证所有记忆都被存储
        assert len(stored_ids) == 3
        assert all(mid == "mem_001" for mid in stored_ids)  # mock返回相同ID
        
        # 验证Mem0被正确调用
        assert mock_mem0_client.add.call_count == 3

    async def test_error_handling_in_integration(self, message_processor, mock_mem0_client):
        """测试集成流程中的错误处理"""
        # 模拟Mem0服务错误
        mock_mem0_client.add.side_effect = Exception("Mem0连接失败")
        
        # 处理有问题的消息
        problematic_update = {
            "user_id": "test_user",
            "content": "测试错误处理",
            "source": "conversation"
        }
        
        # 应该优雅处理错误，不抛出异常
        result = await message_processor.process_memory_update(problematic_update)
        
        # 验证错误处理
        assert result is None or "error" in result
        mock_mem0_client.add.assert_called_once()

    async def test_concurrent_memory_processing(self, memory_service):
        """测试并发记忆处理"""
        user_id = "test_user"
        
        # 并发存储多条记忆
        concurrent_tasks = [
            memory_service.store_memory(
                user_id=user_id,
                content=f"并发记忆测试 {i}",
                metadata={"test_id": i}
            )
            for i in range(5)
        ]
        
        # 等待所有任务完成
        results = await asyncio.gather(*concurrent_tasks)
        
        # 验证并发处理结果
        assert len(results) == 5
        assert all(result == "mem_001" for result in results)

    async def test_message_format_validation(self, message_processor):
        """测试消息格式验证"""
        # 测试有效消息格式
        valid_message = {
            "user_id": "test_user",
            "content": "有效的记忆内容",
            "source": "conversation",
            "timestamp": 1234567890
        }
        
        result = await message_processor.process_memory_update(valid_message)
        assert result is not None
        assert result.get("memory_id") == "mem_001"
        
        # 测试无效消息格式
        invalid_messages = [
            {},  # 空消息
            {"user_id": "test_user"},  # 缺少content
            {"content": "内容但缺少用户ID"},  # 缺少user_id
        ]
        
        for invalid_msg in invalid_messages:
            result = await message_processor.process_memory_update(invalid_msg)
            # 无效消息应该被拒绝或返回错误
            assert result == {"error": "invalid_message_format"}

    async def test_system_integration_stability(self, message_processor, memory_service):
        """测试系统集成稳定性"""
        test_duration = 1.0  # 秒
        max_messages = 5
        start_time = datetime.now()

        processed_count = 0
        while processed_count < max_messages and (
            datetime.now() - start_time
        ).total_seconds() < test_duration:
            test_message = {
                "user_id": f"user_{processed_count % 3}",
                "content": f"稳定性测试消息 {processed_count}",
                "source": "stability_test",
                "timestamp": int(datetime.now().timestamp()),
            }

            await message_processor.process_memory_update(test_message)
            processed_count += 1

            # 短暂休息避免过载
            await asyncio.sleep(0.01)

        # 验证处理的消息数量达到预期
        assert processed_count == max_messages

import pytest
import json
import asyncio
from unittest.mock import AsyncMock, Mock

from main import AIProcessor, TaskProcessor


class TestRedisIntegration:
    """Redis集成测试"""
    
    @pytest.mark.asyncio
    async def test_redis_connection(self, redis_client):
        """测试Redis连接"""
        # 测试ping命令
        result = await redis_client.ping()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_redis_publish_subscribe(self, redis_client):
        """测试Redis发布/订阅"""
        channel = "test_channel"
        message = "test_message"
        
        # 创建订阅者
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        
        # 发布消息
        await redis_client.publish(channel, message)
        
        # 接收消息
        received = await pubsub.get_message(timeout=1)
        assert received is not None
        assert received["type"] == "subscribe"
        
        received = await pubsub.get_message(timeout=1)
        assert received is not None
        assert received["type"] == "message"
        assert received["data"] == message
        
        await pubsub.unsubscribe(channel)
        await pubsub.close()
    
    @pytest.mark.asyncio
    async def test_redis_list_operations(self, redis_client):
        """测试Redis列表操作"""
        key = "test_list"
        values = ["value1", "value2", "value3"]
        
        # 清空列表
        await redis_client.delete(key)
        
        # 添加值到列表
        for value in values:
            await redis_client.lpush(key, value)
        
        # 获取列表长度
        length = await redis_client.llen(key)
        assert length == len(values)
        
        # 获取列表所有值
        retrieved_values = await redis_client.lrange(key, 0, -1)
        assert len(retrieved_values) == len(values)
        
        # 清空列表
        await redis_client.delete(key)
    
    @pytest.mark.asyncio
    async def test_ai_processor_with_real_redis(self, redis_client, sample_config):
        """测试AI处理器与真实Redis的集成"""
        # 保存原始Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        
        # 设置真实Redis客户端
        main_module.redis_client = redis_client
        
        # 创建AI处理器
        ai_processor = AIProcessor()
        
        # 测试获取空的全局上下文
        context = await ai_processor._get_global_context()
        assert isinstance(context, list)
        assert len(context) == 0
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
    
    @pytest.mark.asyncio
    async def test_task_processor_with_real_redis(self, redis_client, sample_config):
        """测试任务处理器与真实Redis的集成"""
        # 保存原始Redis客户端
        import main as main_module
        original_redis_client = main_module.redis_client
        
        # 设置真实Redis客户端
        main_module.redis_client = redis_client
        
        # 创建任务处理器
        task_processor = TaskProcessor()
        
        # 测试发送响应
        task_id = "test_task"
        text = "测试响应"
        await task_processor._send_response(task_id, text, None)
        
        # 验证消息已发布
        # 注意：由于是发布到特定频道，我们无法直接验证
        # 但在实际应用中，这会触发订阅者的回调
        
        # 恢复原始Redis客户端
        main_module.redis_client = original_redis_client
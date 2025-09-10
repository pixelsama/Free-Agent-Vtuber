"""
TDD循环4：长期记忆请求处理测试

测试ltm_requests队列的消费和处理逻辑
"""
import asyncio
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

pytestmark = pytest.mark.asyncio

from src.services.request_processor import LTMRequestProcessor
from src.core.redis_client import RedisMessageBus


@pytest.fixture
def mock_redis_client():
    """模拟Redis客户端"""
    client = AsyncMock()
    # 配置需要的方法
    client.publish = AsyncMock()
    client.brpop = AsyncMock()
    return client


@pytest.fixture 
def mock_mem0_client():
    """模拟Mem0客户端"""
    client = AsyncMock()
    # 模拟搜索返回结果
    client.search.return_value = [
        {
            "id": "mem_001",
            "memory": "用户喜欢看动漫，特别是《进击的巨人》",
            "score": 0.95,
            "metadata": {
                "user_id": "test_user",
                "category": "preference",
                "timestamp": 1234567890
            }
        }
    ]
    # 模拟添加记忆返回ID
    client.add.return_value = "mem_new_001"
    return client


@pytest.fixture
def mock_profile_service():
    """模拟用户画像服务"""
    service = AsyncMock()
    service.get_user_profile.return_value = {
        "user_id": "test_user",
        "preferences": ["动漫", "编程"],
        "personality_traits": ["内向", "好学"],
        "context_info": ["软件工程师", "大学生"],
        "updated_at": datetime.now().isoformat()
    }
    return service


@pytest.fixture
def request_processor(mock_redis_client, mock_mem0_client, mock_profile_service):
    """请求处理器实例"""
    processor = LTMRequestProcessor(
        redis_client=mock_redis_client,
        mem0_client=mock_mem0_client,
        profile_service=mock_profile_service
    )
    return processor


class TestLTMRequestProcessor:
    """长期记忆请求处理器测试类"""
    
    async def test_process_search_request(self, request_processor, mock_redis_client):
        """测试处理搜索请求 - TDD循环4核心测试"""
        # 准备搜索请求
        request = {
            "request_id": "req_1234567890", 
            "type": "search",
            "user_id": "test_user",
            "data": {
                "query": "用户的兴趣爱好",
                "limit": 5
            },
            "timestamp": int(datetime.now().timestamp())
        }
        
        # 处理请求
        response = await request_processor.process_request(request)
        
        # 验证响应结构
        assert response is not None
        assert response["request_id"] == "req_1234567890"
        assert response["status"] == "success"
        assert "memories" in response
        assert len(response["memories"]) > 0
        
        # 验证记忆内容
        memory = response["memories"][0]
        assert "id" in memory
        assert "memory" in memory
        assert "score" in memory
        assert memory["score"] > 0.8
        
        # 注意：process_request方法本身不会发布消息，发布是在_consume_single_message中进行的
        # 这里我们只验证响应的正确性
        assert response["timestamp"] is not None

    async def test_process_add_memory_request(self, request_processor, mock_redis_client, mock_mem0_client):
        """测试处理添加记忆请求"""
        # 准备添加记忆请求
        request = {
            "request_id": "req_add_001",
            "type": "add_memory",
            "user_id": "test_user", 
            "data": {
                "content": "用户最近开始学习React框架",
                "metadata": {
                    "source": "conversation",
                    "category": "learning"
                }
            }
        }
        
        # 处理请求
        response = await request_processor.process_request(request)
        
        # 验证响应
        assert response["status"] == "success"
        assert "memory_id" in response
        assert response["memory_id"] == "mem_new_001"
        
        # 验证Mem0客户端被调用
        mock_mem0_client.add.assert_called_once()
        add_call_args = mock_mem0_client.add.call_args[1]
        assert add_call_args["messages"] == "用户最近开始学习React框架"
        assert add_call_args["user_id"] == "test_user"
        
    async def test_process_profile_get_request(self, request_processor, mock_redis_client, mock_profile_service):
        """测试处理获取用户画像请求"""
        # 准备获取画像请求
        request = {
            "request_id": "req_profile_001",
            "type": "profile_get", 
            "user_id": "test_user",
            "data": {}
        }
        
        # 处理请求
        response = await request_processor.process_request(request)
        
        # 验证响应
        assert response["status"] == "success"
        assert "user_profile" in response
        profile = response["user_profile"]
        assert profile["user_id"] == "test_user"
        assert "preferences" in profile
        assert "personality_traits" in profile
        assert "context_info" in profile
        
        # 验证画像服务被调用
        mock_profile_service.get_user_profile.assert_called_once_with("test_user")

    async def test_process_invalid_request_type(self, request_processor):
        """测试处理无效请求类型"""
        # 准备无效请求
        request = {
            "request_id": "req_invalid_001",
            "type": "invalid_type",
            "user_id": "test_user",
            "data": {}
        }
        
        # 处理请求
        response = await request_processor.process_request(request)
        
        # 验证错误响应
        assert response["status"] == "error"
        assert "error_message" in response
        assert "不支持的请求类型" in response["error_message"]

    async def test_queue_consumer_loop(self, request_processor, mock_redis_client):
        """测试队列消费循环"""
        # 模拟队列消息
        test_request = {
            "request_id": "req_queue_001",
            "type": "search",
            "user_id": "test_user",
            "data": {"query": "测试查询", "limit": 3}
        }
        
        # 模拟brpop返回
        mock_redis_client.brpop.return_value = ("ltm_requests", json.dumps(test_request))
        
        # 启动消费者（模拟一次循环）
        with patch.object(request_processor, 'process_request') as mock_process:
            mock_process.return_value = {"request_id": "req_queue_001", "status": "success"}
            
            # 执行一次消费循环
            await request_processor._consume_single_message()
            
            # 验证处理被调用
            mock_process.assert_called_once_with(test_request)
            
            # 验证响应被发布
            mock_redis_client.publish.assert_called_once()
            publish_call = mock_redis_client.publish.call_args
            assert publish_call[0][0] == "ltm_responses"

    @pytest.mark.parametrize(
        "invalid_request,missing_field",
        [
            pytest.param(
                {"type": "search", "user_id": "test_user", "data": {}},
                "request_id",
                id="missing_request_id",
            ),
            pytest.param(
                {"request_id": "req_001", "user_id": "test_user", "data": {}},
                "type",
                id="missing_type",
            ),
            pytest.param(
                {"request_id": "req_001", "type": "search", "data": {}},
                "user_id",
                id="missing_user_id",
            ),
            pytest.param(
                {"request_id": "req_001", "type": "search", "user_id": "test_user"},
                "data",
                id="missing_data",
            ),
        ],
    )
    async def test_request_validation(self, request_processor, invalid_request, missing_field):
        """测试请求验证逻辑"""
        response = await request_processor.process_request(invalid_request)
        assert response["status"] == "error"
        assert response["error_message"] == f"缺少必要字段: {missing_field}"

    async def test_concurrent_request_processing(self, request_processor):
        """测试并发请求处理能力"""
        # 准备多个并发请求
        requests = [
            {
                "request_id": f"req_concurrent_{i}",
                "type": "search", 
                "user_id": f"user_{i}",
                "data": {"query": f"查询{i}", "limit": 3}
            }
            for i in range(5)
        ]
        
        # 并发处理请求
        tasks = [request_processor.process_request(req) for req in requests]
        responses = await asyncio.gather(*tasks)
        
        # 验证所有请求都被正确处理
        assert len(responses) == 5
        for i, response in enumerate(responses):
            assert response["request_id"] == f"req_concurrent_{i}"
            assert response["status"] == "success"

    async def test_error_handling_and_recovery(self, request_processor, mock_mem0_client):
        """测试错误处理和恢复机制"""
        # 模拟Mem0客户端异常
        mock_mem0_client.search.side_effect = Exception("Mem0连接失败")
        
        request = {
            "request_id": "req_error_001",
            "type": "search",
            "user_id": "test_user", 
            "data": {"query": "测试查询", "limit": 5}
        }
        
        # 处理请求
        response = await request_processor.process_request(request)
        
        # 验证错误被正确处理
        assert response["status"] == "error"
        assert "error_message" in response
        assert "Mem0连接失败" in response["error_message"]
        assert response["request_id"] == "req_error_001"
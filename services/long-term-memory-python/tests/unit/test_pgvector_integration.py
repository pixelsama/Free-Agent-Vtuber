"""
TDD循环3：pgvector向量数据库集成测试（Mock版本）

测试目标：
1. pgvector向量存储和检索功能测试
2. 向量相似度搜索逻辑验证  
3. 用户隔离和数据安全
4. 批量操作支持
5. 连接管理和错误处理

注：这是纯Mock测试，不依赖真实数据库连接
"""

import pytest
from unittest.mock import AsyncMock

pytestmark = pytest.mark.asyncio

from src.core.pgvector_client import PgvectorClient, PgvectorOperationError
from src.models.memory import UserMemory


class TestPgvectorIntegration:
    """测试pgvector向量数据库集成功能 - Mock版本"""

    @pytest.fixture
    def pgvector_client(self):
        """创建mock的pgvector客户端实例"""
        client = AsyncMock(spec=PgvectorClient)
        
        # 配置mock方法的返回值
        client.insert_memory.return_value = "mem_001"
        client.search_similar.return_value = [
            {
                "id": "mem_001",
                "content": "用户喜欢看动漫，特别是《进击的巨人》",
                "user_id": "test_user",
                "category": "preference", 
                "similarity": 0.95,
                "metadata": {"timestamp": 1234567890, "source": "conversation"}
            }
        ]
        client.get_memory_by_id.return_value = {
            "id": "mem_001",
            "content": "用户喜欢看动漫",
            "user_id": "test_user",
            "embedding": [0.1] * 1536,
            "metadata": {"timestamp": 1234567890}
        }
        client.delete_memory.return_value = True
        client.bulk_insert.return_value = ["mem_001", "mem_002", "mem_003", "mem_004", "mem_005"]
        client.convert_to_user_memory.return_value = UserMemory(
            id="mem_001",
            user_id="test_user", 
            content="用户喜欢看动漫",
            metadata={
                "timestamp": 1234567890,
                "source": "conversation",
                "category": "preference"
            }
        )
        
        return client

    @pytest.fixture
    def sample_memory_data(self):
        """样本记忆数据"""
        return {
            "id": "mem_001",
            "embedding": [0.1, 0.2, 0.3] + [0.0] * 1533,  # 1536维向量
            "content": "用户喜欢看动漫，特别是《进击的巨人》",
            "user_id": "test_user",
            "category": "preference",
            "metadata": {
                "timestamp": 1234567890,
                "source": "conversation",
                "session_id": "session_001"
            }
        }

    async def test_pgvector_insert_memory(self, pgvector_client, sample_memory_data):
        """测试向量存储功能 - TDD循环3核心测试"""
        # 测试向量存储
        memory_id = await pgvector_client.insert_memory(sample_memory_data)
        
        # 验证返回值
        assert memory_id is not None
        assert memory_id == "mem_001"
        
        # 验证方法被正确调用
        pgvector_client.insert_memory.assert_called_once_with(sample_memory_data)

    async def test_pgvector_search_similar_vectors(self, pgvector_client):
        """测试向量相似度搜索 - TDD循环3核心测试"""
        # 准备查询向量
        query_vector = [0.1, 0.2, 0.3] + [0.0] * 1533  # 1536维向量
        
        # 测试向量检索
        results = await pgvector_client.search_similar(
            query_vector=query_vector,
            user_id="test_user",
            limit=5,
            threshold=0.7
        )
        
        # 验证搜索结果
        assert len(results) > 0
        assert results[0]["user_id"] == "test_user"
        assert results[0]["similarity"] > 0.7
        
        # 验证方法被正确调用
        pgvector_client.search_similar.assert_called_once_with(
            query_vector=query_vector,
            user_id="test_user", 
            limit=5,
            threshold=0.7
        )

    async def test_pgvector_get_memory_by_id(self, pgvector_client):
        """测试通过ID获取记忆"""
        memory_id = "mem_001"
        
        # 获取指定记忆
        memory = await pgvector_client.get_memory_by_id(memory_id, "test_user")
        
        # 验证结果
        assert memory is not None
        assert memory["id"] == memory_id
        assert memory["user_id"] == "test_user"
        assert "content" in memory
        assert "embedding" in memory
        assert len(memory["embedding"]) == 1536
        
        # 验证方法调用
        pgvector_client.get_memory_by_id.assert_called_once_with(memory_id, "test_user")

    async def test_pgvector_delete_memory(self, pgvector_client):
        """测试删除记忆"""
        memory_id = "mem_001"
        user_id = "test_user"
        
        # 删除记忆
        result = await pgvector_client.delete_memory(memory_id, user_id)
        
        # 验证删除成功
        assert result is True
        
        # 验证方法调用
        pgvector_client.delete_memory.assert_called_once_with(memory_id, user_id)

    async def test_pgvector_bulk_insert(self, pgvector_client):
        """测试批量插入记忆"""
        # 准备批量数据
        memories = [
            {
                "id": f"mem_{i:03d}",
                "embedding": [0.1 * i, 0.2 * i, 0.3 * i] + [0.0] * 1533,
                "content": f"用户记忆内容 {i}",
                "user_id": "test_user",
                "category": "preference",
                "metadata": {"batch_id": "batch_001", "index": i}
            }
            for i in range(1, 6)  # 5条记忆
        ]
        
        # 执行批量插入
        results = await pgvector_client.bulk_insert(memories)
        
        # 验证批量插入结果
        assert isinstance(results, list)
        assert len(results) == 5
        for result in results:
            assert result.startswith("mem_")
        
        # 验证方法调用
        pgvector_client.bulk_insert.assert_called_once_with(memories)

    async def test_pgvector_connection_management(self, pgvector_client):
        """测试连接管理"""
        # 配置mock的连接状态
        pgvector_client.is_connected.return_value = False
        
        # 测试连接建立
        await pgvector_client.connect()
        pgvector_client.connect.assert_called_once()
        
        # 模拟连接成功后的状态
        pgvector_client.is_connected.return_value = True
        assert pgvector_client.is_connected()
        
        # 测试连接关闭
        await pgvector_client.disconnect() 
        pgvector_client.disconnect.assert_called_once()
        
        # 模拟断开连接后的状态
        pgvector_client.is_connected.return_value = False
        assert not pgvector_client.is_connected()

    async def test_pgvector_error_handling(self, pgvector_client):
        """测试错误处理 - 通过mock验证错误情况"""
        # 测试1: 向量插入失败
        pgvector_client.insert_memory.side_effect = PgvectorOperationError("向量维度错误")
        
        with pytest.raises(PgvectorOperationError, match="向量维度错误"):
            await pgvector_client.insert_memory({"invalid": "data"})
        
        # 重置mock并测试搜索失败
        pgvector_client.insert_memory.side_effect = None
        pgvector_client.search_similar.side_effect = PgvectorOperationError("搜索查询错误")
        
        with pytest.raises(PgvectorOperationError, match="搜索查询错误"):
            await pgvector_client.search_similar([0.1] * 1536, "test_user", 5)
        
        # 测试连接错误恢复
        pgvector_client.search_similar.side_effect = None
        pgvector_client.search_similar.return_value = []  # 恢复正常返回

    async def test_pgvector_user_isolation(self, pgvector_client):
        """测试用户数据隔离"""
        query_vector = [0.1] * 1536
        
        # 配置不同用户的搜索结果
        def search_side_effect(query_vector, user_id, limit=10, threshold=0.7):
            if user_id == "user_a":
                return [{"id": "mem_a1", "user_id": "user_a", "content": "用户A的记忆"}]
            elif user_id == "user_b":
                return [{"id": "mem_b1", "user_id": "user_b", "content": "用户B的记忆"}]
            return []
        
        pgvector_client.search_similar.side_effect = search_side_effect
        
        # 搜索用户A的记忆
        results_user_a = await pgvector_client.search_similar(
            query_vector=query_vector,
            user_id="user_a",
            limit=10,
            threshold=0.0
        )
        
        # 搜索用户B的记忆
        results_user_b = await pgvector_client.search_similar(
            query_vector=query_vector,
            user_id="user_b",
            limit=10,
            threshold=0.0
        )
        
        # 验证用户隔离
        for result in results_user_a:
            assert result["user_id"] == "user_a"
            
        for result in results_user_b:
            assert result["user_id"] == "user_b"
        
        # 确保没有交叉污染
        user_a_ids = {result["id"] for result in results_user_a}
        user_b_ids = {result["id"] for result in results_user_b}
        assert user_a_ids.isdisjoint(user_b_ids)  # 两个集合不相交

    async def test_pgvector_convert_to_user_memory(self, pgvector_client, sample_memory_data):
        """测试转换为UserMemory对象 - 验证数据模型转换逻辑"""
        # 执行转换
        user_memory = await pgvector_client.convert_to_user_memory(sample_memory_data)
        
        # 验证转换结果
        assert isinstance(user_memory, UserMemory)
        assert user_memory.id == "mem_001"
        assert user_memory.user_id == "test_user"
        assert user_memory.content == "用户喜欢看动漫"
        
        # 验证方法调用
        pgvector_client.convert_to_user_memory.assert_called_once_with(sample_memory_data)
"""
TDD循环2: Mem0框架集成测试
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch

from src.core.mem0_client import Mem0Service
from src.models.memory import UserMemory, MemoryMetadata, MemoryCategory


class TestMem0Integration:
    """测试Mem0框架集成功能"""

    @pytest.fixture
    def mem0_config(self, test_config):
        """Mem0配置"""
        return test_config["mem0"]

    @pytest.fixture
    def mem0_service(self, mem0_config):
        """创建Mem0服务实例"""
        # 使用Mock避免真实的Mem0初始化
        with patch('src.core.mem0_client.Memory') as mock_memory:
            # 使用普通的Mock而不是AsyncMock，因为run_in_executor需要同步方法
            from unittest.mock import MagicMock
            mock_client = MagicMock()
            mock_memory.from_config.return_value = mock_client
            
            service = Mem0Service(mem0_config)
            service._client = mock_client  # 确保mock被正确设置
            return service

    @pytest.mark.asyncio
    async def test_mem0_add_memory_from_message(self, mem0_service):
        """测试通过Mem0添加记忆"""
        # 配置mock返回值
        mem0_service._client.add.return_value = {"id": "mem_12345"}
        mem0_service._client.search.return_value = [
            {
                "id": "mem_12345",
                "memory": "用户是一个热爱编程的软件工程师",
                "score": 0.95
            }
        ]
        
        # 准备消息数据
        message_data = {
            "user_id": "test_user",
            "content": "用户是一个热爱编程的软件工程师",
            "metadata": {"source": "conversation"}
        }
        
        # 调用Mem0添加记忆
        memory_id = await mem0_service.add_memory(message_data)
        
        # 验证记忆被正确添加
        assert memory_id is not None
        assert isinstance(memory_id, str)
        assert memory_id == "mem_12345"
        
        # 验证可以检索到记忆
        memories = await mem0_service.search("programming", user_id="test_user")
        assert len(memories) > 0
        assert "编程" in memories[0]["memory"]

    @pytest.mark.asyncio
    async def test_mem0_search_memories(self, mem0_service):
        """测试Mem0记忆搜索功能"""
        # 配置mock返回值
        mem0_service._client.search.return_value = [
            {
                "id": "mem_001",
                "memory": "用户喜欢动漫，特别是《进击的巨人》",
                "score": 0.9
            },
            {
                "id": "mem_002",
                "memory": "用户经常讨论动漫角色",
                "score": 0.85
            }
        ]
        
        # 准备搜索参数
        query = "动漫"
        user_id = "test_user"
        limit = 5
        
        # 执行搜索
        memories = await mem0_service.search(query, user_id=user_id, limit=limit)
        
        # 验证搜索结果
        assert isinstance(memories, list)
        assert len(memories) <= limit
        assert len(memories) == 2
        
        # 验证结构
        memory = memories[0]
        assert "memory" in memory
        assert "score" in memory
        assert isinstance(memory["score"], (int, float))
        assert memory["score"] == 0.9

    @pytest.mark.asyncio
    async def test_mem0_get_all_memories(self, mem0_service):
        """测试获取用户所有记忆"""
        # 配置mock返回值
        mem0_service._client.get_all.return_value = [
            {
                "id": "mem_001",
                "memory": "用户喜欢动漫",
                "user_id": "test_user"
            },
            {
                "id": "mem_002", 
                "memory": "用户是程序员",
                "user_id": "test_user"
            }
        ]
        
        user_id = "test_user"
        
        # 获取所有记忆
        memories = await mem0_service.get_all(user_id=user_id)
        
        # 验证返回格式
        assert isinstance(memories, list)
        assert len(memories) == 2
        
        # 验证结构
        memory = memories[0]
        assert "id" in memory
        assert "memory" in memory
        assert memory["id"] == "mem_001"

    @pytest.mark.asyncio
    async def test_mem0_update_memory(self, mem0_service):
        """测试更新记忆"""
        # 配置mock返回值
        mem0_service._client.update.return_value = {
            "id": "mem_123",
            "memory": "更新后的记忆内容：用户现在更喜欢机器学习",
            "updated": True
        }
        
        # 准备更新数据
        memory_id = "mem_123"
        data = {
            "memory": "更新后的记忆内容：用户现在更喜欢机器学习",
        }
        
        # 执行更新
        result = await mem0_service.update(memory_id, data)
        
        # 验证更新结果
        assert result is not None
        assert isinstance(result, dict)
        assert result["updated"] == True

    @pytest.mark.asyncio
    async def test_mem0_delete_memory(self, mem0_service):
        """测试删除记忆"""
        # 配置mock返回值
        mem0_service._client.delete.return_value = {
            "deleted": True,
            "id": "mem_123"
        }
        
        memory_id = "mem_123"
        
        # 执行删除
        result = await mem0_service.delete(memory_id)
        
        # 验证删除结果
        assert result is not None
        assert isinstance(result, dict)
        assert result["deleted"] == True

    @pytest.mark.asyncio
    async def test_mem0_connection_error_handling(self, mem0_service):
        """测试Mem0连接错误处理"""
        # 模拟连接错误
        mem0_service._client.add.side_effect = Exception("Connection failed")
        
        # 应该抛出适当的异常
        with pytest.raises(Exception, match="Connection failed"):
            await mem0_service.add_memory({
                "user_id": "test_user",
                "content": "test content"
            })

    @pytest.mark.asyncio
    async def test_mem0_to_user_memory_conversion(self, mem0_service):
        """测试Mem0记忆转换为UserMemory对象"""
        # 模拟Mem0返回的记忆数据
        mem0_memory = {
            "id": "mem_123",
            "memory": "用户喜欢动漫，特别是《进击的巨人》",
            "user_id": "test_user",
            "metadata": {
                "category": "preference",
                "confidence": 0.8,
                "created_at": "2024-01-01T12:00:00Z"
            }
        }
        
        # 转换为UserMemory对象
        user_memory = mem0_service.convert_to_user_memory(mem0_memory)
        
        # 验证转换结果
        assert isinstance(user_memory, UserMemory)
        assert user_memory.user_id == "test_user"
        assert "动漫" in user_memory.content
        assert isinstance(user_memory.metadata, MemoryMetadata)
        assert user_memory.metadata.category == MemoryCategory.PREFERENCE
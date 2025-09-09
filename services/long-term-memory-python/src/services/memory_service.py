"""
记忆管理服务

提供高级记忆管理功能，包括存储、搜索、关联等操作
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.mem0_client import Mem0Service


class MemoryService:
    """记忆管理服务"""
    
    def __init__(self, mem0_client, redis_client):
        self.mem0_client = mem0_client
        self.redis_client = redis_client
        self.logger = logging.getLogger(__name__)

    async def store_memory(self, user_id: str, content: str, 
                          metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        存储用户记忆
        
        Args:
            user_id: 用户ID
            content: 记忆内容
            metadata: 元数据
            
        Returns:
            记忆ID
        """
        try:
            # 准备元数据
            if metadata is None:
                metadata = {}
                
            metadata.update({
                "created_at": datetime.now().isoformat(),
                "service": "memory_service"
            })
            
            # 使用Mem0存储记忆
            memory_id = await self.mem0_client.add(
                messages=content,
                user_id=user_id,
                metadata=metadata
            )
            
            self.logger.info(f"记忆已存储: {memory_id} for user: {user_id}")
            return memory_id
            
        except Exception as e:
            self.logger.error(f"存储记忆失败: {e}")
            raise

    async def search_related_memories(self, user_id: str, query: str, 
                                    limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索相关记忆
        
        Args:
            user_id: 用户ID
            query: 搜索查询
            limit: 结果限制
            
        Returns:
            相关记忆列表
        """
        try:
            # 使用Mem0搜索
            results = await self.mem0_client.search(
                query=query,
                user_id=user_id,
                limit=limit
            )
            
            self.logger.info(f"找到 {len(results)} 条相关记忆")
            return results
            
        except Exception as e:
            self.logger.error(f"搜索记忆失败: {e}")
            return []

    async def get_user_memories(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取用户的所有记忆
        
        Args:
            user_id: 用户ID
            limit: 结果限制
            
        Returns:
            用户记忆列表
        """
        try:
            # 使用空查询获取所有记忆
            memories = await self.mem0_client.get_all(
                user_id=user_id,
                limit=limit
            )
            
            return memories
            
        except Exception as e:
            self.logger.error(f"获取用户记忆失败: {e}")
            return []

    async def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """
        删除指定记忆
        
        Args:
            memory_id: 记忆ID
            user_id: 用户ID
            
        Returns:
            是否删除成功
        """
        try:
            await self.mem0_client.delete(memory_id=memory_id)
            self.logger.info(f"记忆已删除: {memory_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"删除记忆失败: {e}")
            return False
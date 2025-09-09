"""
用户画像服务

基于用户记忆数据构建和管理用户画像
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from ..models.profile import UserProfile, ProfileBuilder


class ProfileService:
    """用户画像服务"""
    
    def __init__(self, mem0_client, redis_client):
        self.mem0_client = mem0_client
        self.redis_client = redis_client
        self.profile_builder = ProfileBuilder()
        self.logger = logging.getLogger(__name__)

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户画像
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户画像数据
        """
        try:
            # 检查缓存中的画像
            cached_profile = await self._get_cached_profile(user_id)
            if cached_profile:
                return cached_profile
            
            # 从记忆数据构建画像
            memories = await self._get_user_memories(user_id)
            profile = await self.profile_builder.build_profile(user_id, memories)
            
            # 缓存画像
            await self._cache_profile(user_id, profile)
            
            return profile
            
        except Exception as e:
            self.logger.error(f"获取用户画像失败 {user_id}: {e}")
            # 返回基础画像结构
            return self._create_empty_profile(user_id)

    async def _get_user_memories(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """获取用户的记忆数据"""
        try:
            # 使用Mem0搜索用户的所有记忆
            memories = await self.mem0_client.search(
                query="",  # 空查询获取所有记忆
                user_id=user_id,
                limit=limit
            )
            return memories or []
        except Exception as e:
            self.logger.error(f"获取用户记忆失败 {user_id}: {e}")
            return []

    async def _get_cached_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """从缓存获取用户画像"""
        try:
            cache_key = f"user_profile:{user_id}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                import json
                return json.loads(cached_data)
        except Exception as e:
            self.logger.debug(f"获取缓存画像失败 {user_id}: {e}")
        return None

    async def _cache_profile(self, user_id: str, profile: Dict[str, Any], ttl: int = 3600):
        """缓存用户画像"""
        try:
            cache_key = f"user_profile:{user_id}"
            import json
            await self.redis_client.setex(cache_key, ttl, json.dumps(profile))
        except Exception as e:
            self.logger.error(f"缓存用户画像失败 {user_id}: {e}")

    def _create_empty_profile(self, user_id: str) -> Dict[str, Any]:
        """创建空的用户画像"""
        return {
            "user_id": user_id,
            "preferences": [],
            "personality_traits": [],
            "context_info": [],
            "updated_at": datetime.now().isoformat(),
            "version": "1.0"
        }
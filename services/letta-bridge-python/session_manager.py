import asyncio
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis
import time
from letta_client import LettaClient, LettaAPIError

logger = logging.getLogger(__name__)

class SessionManager:
    """用户会话管理器 - 管理user_id到Letta agent的映射"""
    
    def __init__(self, redis_client: redis.Redis, letta_client: LettaClient, config: Dict[str, Any]):
        self.redis_client = redis_client
        self.letta_client = letta_client
        self.config = config
        
        # 配置项
        self.agent_mapping_key = config.get("session", {}).get("agent_mapping_key", "letta:user_agent_mapping")
        self.session_ttl_hours = config.get("session", {}).get("session_ttl_hours", 24)
        self.agent_creation_timeout = config.get("bridge", {}).get("agent_creation_timeout", 60)
        
        # 本地缓存，减少Redis查询
        self._local_cache: Dict[str, str] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 本地缓存5分钟
        self._creation_locks: Dict[str, asyncio.Lock] = {}
    
    async def get_or_create_agent(self, user_id: str) -> str:
        """获取或创建用户对应的Letta agent ID"""
        try:
            # 1. 检查本地缓存
            cached_agent_id = self._get_from_local_cache(user_id)
            if cached_agent_id:
                return cached_agent_id
            
            # 2. 检查Redis缓存
            redis_agent_id = await self._get_from_redis_cache(user_id)
            if redis_agent_id:
                # 验证agent是否仍然存在
                if await self._validate_agent_exists(redis_agent_id):
                    self._update_local_cache(user_id, redis_agent_id)
                    return redis_agent_id
                else:
                    # agent不存在，清除缓存
                    await self._remove_from_redis_cache(user_id)
            
            # 3. 创建新的agent
            agent_id = await self._create_agent_for_user(user_id)
            
            # 4. 缓存结果
            await self._update_redis_cache(user_id, agent_id)
            self._update_local_cache(user_id, agent_id)
            
            return agent_id
            
        except Exception as e:
            logger.error(f"Failed to get or create agent for user {user_id}: {e}")
            raise
    
    def _get_from_local_cache(self, user_id: str) -> Optional[str]:
        """从本地缓存获取agent ID"""
        if user_id not in self._local_cache:
            return None
        
        # 检查缓存是否过期
        cache_time = self._cache_timestamps.get(user_id, 0)
        if time.time() - cache_time > self._cache_ttl:
            # 缓存过期，清除
            self._local_cache.pop(user_id, None)
            self._cache_timestamps.pop(user_id, None)
            return None
        
        return self._local_cache[user_id]
    
    def _update_local_cache(self, user_id: str, agent_id: str):
        """更新本地缓存"""
        self._local_cache[user_id] = agent_id
        self._cache_timestamps[user_id] = time.time()
    
    async def _get_from_redis_cache(self, user_id: str) -> Optional[str]:
        """从Redis缓存获取agent ID"""
        try:
            agent_id = await self.redis_client.hget(self.agent_mapping_key, user_id)
            return agent_id
        except Exception as e:
            logger.error(f"Error reading from Redis cache for user {user_id}: {e}")
            return None
    
    async def _update_redis_cache(self, user_id: str, agent_id: str):
        """更新Redis缓存"""
        try:
            # 设置映射关系
            await self.redis_client.hset(self.agent_mapping_key, user_id, agent_id)
            
            # 设置过期时间
            await self.redis_client.expire(self.agent_mapping_key, self.session_ttl_hours * 3600)
            
            logger.debug(f"Updated Redis cache: {user_id} -> {agent_id}")
        except Exception as e:
            logger.error(f"Error updating Redis cache for user {user_id}: {e}")
    
    async def _remove_from_redis_cache(self, user_id: str):
        """从Redis缓存移除映射"""
        try:
            await self.redis_client.hdel(self.agent_mapping_key, user_id)
            # 同时清除本地缓存
            self._local_cache.pop(user_id, None)
            self._cache_timestamps.pop(user_id, None)
            logger.debug(f"Removed Redis cache for user {user_id}")
        except Exception as e:
            logger.error(f"Error removing Redis cache for user {user_id}: {e}")
    
    async def _validate_agent_exists(self, agent_id: str) -> bool:
        """验证agent是否仍然存在"""
        try:
            agent_info = await self.letta_client.get_agent(agent_id)
            return agent_info is not None
        except Exception as e:
            logger.warning(f"Error validating agent {agent_id}: {e}")
            return False
    
    async def _create_agent_for_user(self, user_id: str) -> str:
        """为用户创建新的Letta agent"""
        # 使用锁防止并发创建
        if user_id not in self._creation_locks:
            self._creation_locks[user_id] = asyncio.Lock()
        
        async with self._creation_locks[user_id]:
            # 再次检查缓存，可能在等待锁期间已创建
            cached_agent_id = await self._get_from_redis_cache(user_id)
            if cached_agent_id and await self._validate_agent_exists(cached_agent_id):
                return cached_agent_id
            
            try:
                # 生成agent名称
                agent_name = f"user_{user_id}_{int(time.time())}"
                
                # 从配置获取系统提示
                system_prompt = self._get_system_prompt_for_user(user_id)
                
                logger.info(f"Creating new Letta agent for user {user_id}")
                
                # 创建agent（带超时）
                agent_info = await asyncio.wait_for(
                    self.letta_client.create_agent(agent_name, system_prompt),
                    timeout=self.agent_creation_timeout
                )
                
                agent_id = agent_info["id"]
                logger.info(f"Successfully created agent {agent_id} for user {user_id}")
                
                return agent_id
                
            except asyncio.TimeoutError:
                logger.error(f"Timeout creating agent for user {user_id}")
                raise LettaAPIError(f"Agent creation timeout for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to create agent for user {user_id}: {e}")
                raise
    
    def _get_system_prompt_for_user(self, user_id: str) -> str:
        """获取用户的系统提示词"""
        # 可以根据用户定制系统提示，这里使用默认的
        default_prompt = """你是一个AI虚拟主播助手，具有永久记忆能力。
你的特点：
1. 友善、活泼、有趣
2. 能记住与用户的所有对话历史
3. 会根据过往对话调整回应风格
4. 善于营造轻松愉快的氛围

请始终保持角色一致性，并充分利用你的记忆能力为用户提供个性化的交互体验。"""
        
        # 可以根据配置文件或用户偏好定制
        bridge_config = self.config.get("bridge", {})
        custom_prompt = bridge_config.get("system_prompt")
        
        return custom_prompt if custom_prompt else default_prompt
    
    async def send_message_to_agent(self, user_id: str, message: str) -> Dict[str, Any]:
        """向用户的agent发送消息"""
        try:
            agent_id = await self.get_or_create_agent(user_id)
            
            logger.debug(f"Sending message to agent {agent_id} for user {user_id}")
            
            response = await self.letta_client.send_message(agent_id, message)
            
            logger.debug(f"Received response from agent {agent_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to send message for user {user_id}: {e}")
            raise
    
    async def get_agent_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户agent的信息"""
        try:
            agent_id = await self.get_or_create_agent(user_id)
            return await self.letta_client.get_agent(agent_id)
        except Exception as e:
            logger.error(f"Failed to get agent info for user {user_id}: {e}")
            return None
    
    async def reset_user_agent(self, user_id: str) -> bool:
        """重置用户的agent（删除并重新创建）"""
        try:
            # 获取当前agent ID
            current_agent_id = await self._get_from_redis_cache(user_id)
            
            if current_agent_id:
                # 删除现有agent
                await self.letta_client.delete_agent(current_agent_id)
                logger.info(f"Deleted agent {current_agent_id} for user {user_id}")
            
            # 清除缓存
            await self._remove_from_redis_cache(user_id)
            
            # 创建新agent
            new_agent_id = await self.get_or_create_agent(user_id)
            logger.info(f"Created new agent {new_agent_id} for user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset agent for user {user_id}: {e}")
            return False
    
    async def cleanup_expired_sessions(self):
        """清理过期的会话（可以作为定时任务运行）"""
        try:
            # 获取所有映射
            all_mappings = await self.redis_client.hgetall(self.agent_mapping_key)
            
            if not all_mappings:
                return
            
            logger.info(f"Checking {len(all_mappings)} user sessions for cleanup")
            
            cleaned_count = 0
            for user_id, agent_id in all_mappings.items():
                # 验证agent是否仍存在
                if not await self._validate_agent_exists(agent_id):
                    await self._remove_from_redis_cache(user_id)
                    cleaned_count += 1
                    logger.info(f"Cleaned up invalid session: {user_id} -> {agent_id}")
            
            if cleaned_count > 0:
                logger.info(f"Session cleanup completed: removed {cleaned_count} invalid sessions")
        
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")
    
    async def get_session_stats(self) -> Dict[str, Any]:
        """获取会话统计信息"""
        try:
            all_mappings = await self.redis_client.hgetall(self.agent_mapping_key)
            
            active_sessions = 0
            for user_id, agent_id in all_mappings.items():
                if await self._validate_agent_exists(agent_id):
                    active_sessions += 1
            
            return {
                "total_mappings": len(all_mappings),
                "active_sessions": active_sessions,
                "local_cache_size": len(self._local_cache),
                "creation_locks": len(self._creation_locks)
            }
            
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return {}
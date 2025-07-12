import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import redis.asyncio as redis

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, redis_client: redis.Redis, config: dict):
        self.redis_client = redis_client
        self.config = config
        self.memory_config = config.get("memory", {})
        
        # 配置参数
        self.max_memory_size = self.memory_config.get("max_memory_size", 100)
        self.memory_ttl = self.memory_config.get("memory_ttl_hours", 24) * 3600
        self.context_window = self.memory_config.get("context_window", 20)
        
        # Redis键名
        self.memory_key_prefix = "memory:"
        self.user_memory_key = f"{self.memory_key_prefix}user_sessions"
        self.global_memory_key = f"{self.memory_key_prefix}global_context"
        
        # Pub/Sub频道
        self.memory_update_channel = "memory_updates"
        
    async def store_message(self, user_id: str, message_type: str, content: str, 
                          source: str = "user", require_ai_response: bool = True,
                          metadata: Optional[Dict] = None) -> str:
        """存储消息到记忆中"""
        try:
            message_id = f"{user_id}_{int(time.time() * 1000)}"
            timestamp = datetime.now().isoformat()
            
            message_data = {
                "message_id": message_id,
                "user_id": user_id,
                "type": message_type,
                "content": content,
                "source": source,
                "timestamp": timestamp,
                "require_ai_response": require_ai_response,
                "metadata": metadata or {}
            }
            
            # 存储到用户会话记忆
            await self._store_to_user_memory(user_id, message_data)
            
            # 存储到全局上下文（如果需要）
            if self.memory_config.get("enable_global_context", True):
                await self._store_to_global_memory(message_data)
            
            # 发布记忆更新事件
            if require_ai_response:
                await self._publish_memory_update(message_data)
            
            logger.info(f"Stored message {message_id} from {source}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            raise
    
    async def get_user_context(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        """获取用户的对话上下文"""
        try:
            if limit is None:
                limit = self.context_window
                
            user_key = f"{self.user_memory_key}:{user_id}"
            
            # 获取最近的消息（Redis列表从右侧获取最新消息）
            messages_json = await self.redis_client.lrange(user_key, -limit, -1)
            
            messages = []
            for msg_json in messages_json:
                try:
                    message = json.loads(msg_json)
                    messages.append(message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in user memory: {msg_json}")
                    
            return messages
            
        except Exception as e:
            logger.error(f"Error getting user context for {user_id}: {e}")
            return []
    
    async def get_global_context(self, limit: Optional[int] = None) -> List[Dict]:
        """获取全局对话上下文"""
        try:
            if limit is None:
                limit = self.context_window
                
            messages_json = await self.redis_client.lrange(self.global_memory_key, -limit, -1)
            
            messages = []
            for msg_json in messages_json:
                try:
                    message = json.loads(msg_json)
                    messages.append(message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in global memory: {msg_json}")
                    
            return messages
            
        except Exception as e:
            logger.error(f"Error getting global context: {e}")
            return []
    
    async def clear_user_memory(self, user_id: str) -> bool:
        """清除用户记忆"""
        try:
            user_key = f"{self.user_memory_key}:{user_id}"
            await self.redis_client.delete(user_key)
            logger.info(f"Cleared memory for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing user memory: {e}")
            return False
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        try:
            stats = {
                "global_memory_size": await self.redis_client.llen(self.global_memory_key),
                "active_users": 0,
                "total_user_messages": 0
            }
            
            # 获取所有用户记忆键
            user_keys = await self.redis_client.keys(f"{self.user_memory_key}:*")
            stats["active_users"] = len(user_keys)
            
            # 计算总用户消息数
            for key in user_keys:
                count = await self.redis_client.llen(key)
                stats["total_user_messages"] += count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting memory stats: {e}")
            return {}
    
    async def _store_to_user_memory(self, user_id: str, message_data: Dict):
        """存储到用户记忆"""
        user_key = f"{self.user_memory_key}:{user_id}"
        message_json = json.dumps(message_data, ensure_ascii=False)
        
        # 添加到列表左侧（最新消息）
        await self.redis_client.lpush(user_key, message_json)
        
        # 限制列表长度
        await self.redis_client.ltrim(user_key, 0, self.max_memory_size - 1)
        
        # 设置过期时间
        await self.redis_client.expire(user_key, self.memory_ttl)
    
    async def _store_to_global_memory(self, message_data: Dict):
        """存储到全局记忆"""
        message_json = json.dumps(message_data, ensure_ascii=False)
        
        # 添加到全局列表
        await self.redis_client.lpush(self.global_memory_key, message_json)
        
        # 限制全局记忆大小
        global_limit = self.memory_config.get("global_memory_limit", 1000)
        await self.redis_client.ltrim(self.global_memory_key, 0, global_limit - 1)
    
    async def _publish_memory_update(self, message_data: Dict):
        """发布记忆更新事件"""
        try:
            update_event = {
                "event_type": "memory_update",
                "user_id": message_data["user_id"],
                "message_id": message_data["message_id"],
                "source": message_data["source"],
                "require_ai_response": message_data["require_ai_response"],
                "timestamp": message_data["timestamp"],
                "task_id": message_data.get("metadata", {}).get("task_id")
            }
            
            await self.redis_client.publish(
                self.memory_update_channel, 
                json.dumps(update_event, ensure_ascii=False)
            )
            
            logger.info(f"Published memory update event for message {message_data['message_id']}")
            
        except Exception as e:
            logger.error(f"Error publishing memory update: {e}")
    
    async def cleanup_old_memories(self):
        """清理过期记忆"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.memory_config.get("cleanup_hours", 48))
            cutoff_timestamp = cutoff_time.isoformat()
            
            # 清理全局记忆中的过期消息
            await self._cleanup_memory_list(self.global_memory_key, cutoff_timestamp)
            
            # 清理用户记忆
            user_keys = await self.redis_client.keys(f"{self.user_memory_key}:*")
            for key in user_keys:
                await self._cleanup_memory_list(key, cutoff_timestamp)
            
            logger.info("Completed memory cleanup")
            
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
    
    async def _cleanup_memory_list(self, key: str, cutoff_timestamp: str):
        """清理指定记忆列表中的过期消息"""
        try:
            messages = await self.redis_client.lrange(key, 0, -1)
            valid_messages = []
            
            for msg_json in messages:
                try:
                    message = json.loads(msg_json)
                    if message.get("timestamp", "") >= cutoff_timestamp:
                        valid_messages.append(msg_json)
                except json.JSONDecodeError:
                    continue
            
            # 重新写入有效消息
            if valid_messages != messages:
                await self.redis_client.delete(key)
                if valid_messages:
                    await self.redis_client.lpush(key, *valid_messages)
                    
        except Exception as e:
            logger.error(f"Error cleaning up memory list {key}: {e}")
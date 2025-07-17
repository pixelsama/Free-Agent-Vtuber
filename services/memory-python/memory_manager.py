import asyncio
import json
import logging
import time
import os
import aiohttp
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
        
        # 初始化记忆总结器
        self.summarizer = MemorySummarizer(config)
        
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
        
        # 异步检查是否需要总结（不阻塞主流程）
        asyncio.create_task(self._check_memory_summary(user_key, "user"))
    
    async def _store_to_global_memory(self, message_data: Dict):
        """存储到全局记忆"""
        message_json = json.dumps(message_data, ensure_ascii=False)
        
        # 添加到全局列表
        await self.redis_client.lpush(self.global_memory_key, message_json)
        
        # 限制全局记忆大小
        global_limit = self.memory_config.get("global_memory_limit", 1000)
        await self.redis_client.ltrim(self.global_memory_key, 0, global_limit - 1)
        
        # 异步检查是否需要总结（不阻塞主流程）
        asyncio.create_task(self._check_memory_summary(self.global_memory_key, "global"))
    
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

    async def _check_memory_summary(self, memory_key: str, memory_type: str):
        """检查是否需要进行记忆总结
        
        Args:
            memory_key: Redis记忆键名
            memory_type: 记忆类型 ("user" 或 "global")
        """
        try:
            if not self.memory_config.get("summary", {}).get("enable", False):
                return
            
            # 计算当前记忆的权重总和
            current_weight = await self._calculate_memory_weight(memory_key)
            
            # 确定触发阈值
            if memory_type == "user":
                max_size = self.max_memory_size
            else:  # global
                max_size = self.memory_config.get("global_memory_limit", 1000)
            
            trigger_ratio = self.memory_config.get("summary", {}).get("trigger_ratio", 0.8)
            trigger_threshold = max_size * trigger_ratio
            
            logger.debug(f"Memory {memory_key}: weight={current_weight:.1f}, threshold={trigger_threshold:.1f}")
            
            # 检查是否需要总结
            if current_weight >= trigger_threshold:
                logger.info(f"Memory {memory_key} reached summary threshold, starting summarization")
                await self._perform_memory_summary(memory_key, memory_type)
            
        except Exception as e:
            logger.error(f"Error checking memory summary for {memory_key}: {e}")
    
    async def _calculate_memory_weight(self, memory_key: str) -> float:
        """计算记忆的权重总和
        
        Args:
            memory_key: Redis记忆键名
            
        Returns:
            记忆权重总和
        """
        try:
            # 获取所有记忆项
            messages_json = await self.redis_client.lrange(memory_key, 0, -1)
            
            total_weight = 0.0
            for msg_json in messages_json:
                try:
                    message = json.loads(msg_json)
                    weight = self.summarizer.calculate_memory_weight(message)
                    total_weight += weight
                except json.JSONDecodeError:
                    # 解析失败的消息按1.0权重计算
                    total_weight += 1.0
            
            return total_weight
            
        except Exception as e:
            logger.error(f"Error calculating memory weight for {memory_key}: {e}")
            return 0.0
    
    async def _perform_memory_summary(self, memory_key: str, memory_type: str):
        """执行记忆总结
        
        Args:
            memory_key: Redis记忆键名
            memory_type: 记忆类型 ("user" 或 "global")
        """
        try:
            # 获取所有记忆
            all_messages_json = await self.redis_client.lrange(memory_key, 0, -1)
            
            if not all_messages_json:
                logger.info(f"No memories to summarize for {memory_key}")
                return
            
            # 解析记忆数据
            all_memories = []
            for msg_json in all_messages_json:
                try:
                    memory = json.loads(msg_json)
                    all_memories.append(memory)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in memory: {msg_json[:100]}...")
            
            if not all_memories:
                logger.warning(f"No valid memories found for {memory_key}")
                return
            
            # 计算总结范围
            summarize_ratio = self.memory_config.get("summary", {}).get("summarize_ratio", 0.6)
            summarize_count = int(len(all_memories) * summarize_ratio)
            
            if summarize_count <= 0:
                logger.info(f"Not enough memories to summarize for {memory_key}")
                return
            
            # 分离要总结的记忆和保留的记忆
            # Redis列表是LIFO，索引0是最新的，所以要总结最旧的部分
            memories_to_summarize = all_memories[-summarize_count:]  # 最旧的部分
            memories_to_keep = all_memories[:-summarize_count]       # 最新的部分
            
            logger.info(f"Summarizing {len(memories_to_summarize)} memories, keeping {len(memories_to_keep)} for {memory_key}")
            
            # 调用总结器
            summary_result = await self.summarizer.summarize_memories(memories_to_summarize, memory_key)
            
            if summary_result:
                # 总结成功，替换记忆
                await self._replace_memories_with_summary(memory_key, memories_to_keep, summary_result)
                logger.info(f"Successfully summarized and replaced memories for {memory_key}")
            else:
                # 总结失败，检查是否需要强制截断
                await self._handle_summary_failure(memory_key, memory_type)
                
        except Exception as e:
            logger.error(f"Error performing memory summary for {memory_key}: {e}")
            await self._handle_summary_failure(memory_key, memory_type)
    
    async def _replace_memories_with_summary(self, memory_key: str, kept_memories: List[Dict], summary: Dict):
        """用总结替换记忆
        
        Args:
            memory_key: Redis记忆键名
            kept_memories: 要保留的记忆列表
            summary: 总结数据
        """
        try:
            # 删除原有记忆
            await self.redis_client.delete(memory_key)
            
            # 先添加总结（在最旧位置）
            summary_json = json.dumps(summary, ensure_ascii=False)
            await self.redis_client.lpush(memory_key, summary_json)
            
            # 再添加保留的记忆（按原有顺序，最新的在前面）
            if kept_memories:
                kept_memories_json = [json.dumps(mem, ensure_ascii=False) for mem in kept_memories]
                await self.redis_client.lpush(memory_key, *kept_memories_json)
            
            # 设置过期时间（如果是用户记忆）
            if "user_sessions" in memory_key:
                await self.redis_client.expire(memory_key, self.memory_ttl)
                
            logger.info(f"Replaced memories with summary for {memory_key}")
            
        except Exception as e:
            logger.error(f"Error replacing memories with summary for {memory_key}: {e}")
    
    async def _handle_summary_failure(self, memory_key: str, memory_type: str):
        """处理总结失败的情况
        
        Args:
            memory_key: Redis记忆键名  
            memory_type: 记忆类型 ("user" 或 "global")
        """
        try:
            # 检查记忆是否真的爆满了
            current_count = await self.redis_client.llen(memory_key)
            
            if memory_type == "user":
                max_size = self.max_memory_size
            else:  # global
                max_size = self.memory_config.get("global_memory_limit", 1000)
            
            # 如果记忆数量超过了最大限制的1.2倍，强制截断
            if current_count > max_size * 1.2:
                logger.warning(f"Memory {memory_key} overflow ({current_count} > {max_size * 1.2}), forcing truncation")
                await self.redis_client.ltrim(memory_key, 0, max_size - 1)
                
                # 记录告警
                logger.error(f"ALERT: Memory {memory_key} was force-truncated due to summary failure")
            
        except Exception as e:
            logger.error(f"Error handling summary failure for {memory_key}: {e}")


class MemorySummarizer:
    """记忆总结器，处理记忆内容的AI总结"""
    
    def __init__(self, config: dict):
        """初始化记忆总结器
        
        Args:
            config: 配置字典，包含总结相关配置
        """
        self.config = config
        self.summary_config = config.get("memory", {}).get("summary", {})
        self.ai_config = self.summary_config.get("ai_config", {})
        self.prompts = self.summary_config.get("prompts", {})
        self.retry_states = {}  # 记录重试状态 {memory_key: {attempts: int, last_attempt: timestamp}}
        
        # 优先从环境变量读取API key，如果没有再从配置文件读取
        self.api_key = os.getenv("OPENAI_API_KEY") or self.ai_config.get("api_key")
        if not self.api_key:
            logger.warning("AI API key not configured (set OPENAI_API_KEY environment variable)")
    
    async def summarize_memories(self, memories: List[Dict], memory_key: str) -> Optional[Dict]:
        """总结记忆内容
        
        Args:
            memories: 要总结的记忆列表
            memory_key: 记忆的Redis键名，用于重试状态管理
            
        Returns:
            总结结果字典，失败时返回None
        """
        if not self.summary_config.get("enable", False):
            logger.info("Memory summary is disabled")
            return None
            
        if not self.api_key:
            logger.error("API key not available for memory summarization")
            return None
        
        try:
            # 检查是否在重试冷却期
            if self._is_in_retry_cooldown(memory_key):
                logger.info(f"Memory {memory_key} is in retry cooldown")
                return None
            
            # 调用AI进行总结
            summary_result = await self._call_ai_for_summary(memories)
            
            if summary_result:
                # 成功，清除重试状态
                self._clear_retry_state(memory_key)
                logger.info(f"Successfully summarized {len(memories)} memories for {memory_key}")
                return summary_result
            else:
                # 失败，记录重试状态
                self._record_retry_attempt(memory_key)
                return None
                
        except Exception as e:
            logger.error(f"Error summarizing memories for {memory_key}: {e}")
            self._record_retry_attempt(memory_key)
            return None
    
    async def _call_ai_for_summary(self, memories: List[Dict]) -> Optional[Dict]:
        """调用AI API进行记忆总结
        
        Args:
            memories: 要总结的记忆列表
            
        Returns:
            总结结果字典，失败时返回None
        """
        try:
            # 准备请求数据
            memories_text = json.dumps(memories, ensure_ascii=False, indent=2)
            system_prompt = self.prompts.get("system_prompt", "")
            user_prompt = self.prompts.get("user_prompt_template", "").format(memories=memories_text)
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.ai_config.get("model", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": self.ai_config.get("temperature", 0.3),
                "max_tokens": self.summary_config.get("summary_format", {}).get("max_summary_length", 500)
            }
            
            # 发送请求
            timeout = aiohttp.ClientTimeout(total=self.ai_config.get("timeout", 60))
            max_retries = self.ai_config.get("max_retries", 3)
            
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(
                            f"{self.ai_config.get('base_url', 'https://api.openai.com/v1/')}/chat/completions",
                            headers=headers,
                            json=payload
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                content = result["choices"][0]["message"]["content"]
                                
                                # 尝试解析为JSON
                                try:
                                    summary_data = json.loads(content)
                                    # 添加元数据
                                    summary_data.update({
                                        "type": "memory_summary",
                                        "created_at": datetime.now().isoformat(),
                                        "summarized_count": len(memories),
                                        "compression_ratio": self.summary_config.get("summary_format", {}).get("compression_ratio", 0.3)
                                    })
                                    return summary_data
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse AI response as JSON: {e}")
                                    logger.debug(f"AI response content: {content}")
                                    return None
                            else:
                                error_text = await response.text()
                                logger.error(f"AI API request failed (attempt {attempt + 1}): {response.status} - {error_text}")
                                
                except aiohttp.ClientError as e:
                    logger.error(f"HTTP client error (attempt {attempt + 1}): {e}")
                    
                # 重试前等待
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # 指数退避
            
            logger.error("All AI API retry attempts failed")
            return None
            
        except Exception as e:
            logger.error(f"Unexpected error in AI API call: {e}")
            return None
    
    def _is_in_retry_cooldown(self, memory_key: str) -> bool:
        """检查是否在重试冷却期内
        
        Args:
            memory_key: 记忆键名
            
        Returns:
            是否在冷却期内
        """
        if memory_key not in self.retry_states:
            return False
            
        retry_state = self.retry_states[memory_key]
        attempts = retry_state.get("attempts", 0)
        last_attempt = retry_state.get("last_attempt", 0)
        
        # 检查是否已达到最大重试次数
        max_retries = self.summary_config.get("retry_policy", {}).get("max_retries", 3)
        if attempts >= max_retries:
            return True
        
        # 检查是否在重试间隔内
        retry_intervals = self.summary_config.get("retry_policy", {}).get("retry_intervals_seconds", [3600, 7200, 14400])
        if attempts > 0 and attempts <= len(retry_intervals):
            interval = retry_intervals[attempts - 1] if attempts <= len(retry_intervals) else retry_intervals[-1]
            if time.time() - last_attempt < interval:
                return True
        
        return False
    
    def _record_retry_attempt(self, memory_key: str):
        """记录重试尝试
        
        Args:
            memory_key: 记忆键名
        """
        if memory_key not in self.retry_states:
            self.retry_states[memory_key] = {"attempts": 0, "last_attempt": 0}
        
        self.retry_states[memory_key]["attempts"] += 1
        self.retry_states[memory_key]["last_attempt"] = time.time()
        
        logger.warning(f"Recorded retry attempt {self.retry_states[memory_key]['attempts']} for {memory_key}")
    
    def _clear_retry_state(self, memory_key: str):
        """清除重试状态
        
        Args:
            memory_key: 记忆键名
        """
        if memory_key in self.retry_states:
            del self.retry_states[memory_key]
            logger.info(f"Cleared retry state for {memory_key}")
    
    def calculate_memory_weight(self, memory_item: Dict) -> float:
        """计算记忆项的权重
        
        对于总结类型的记忆，按压缩比例计算权重
        对于普通记忆，权重为1.0
        
        Args:
            memory_item: 记忆项字典
            
        Returns:
            记忆权重
        """
        if memory_item.get("type") == "memory_summary":
            compression_ratio = memory_item.get("compression_ratio", 
                                               self.summary_config.get("summary_format", {}).get("compression_ratio", 0.3))
            summarized_count = memory_item.get("summarized_count", 1)
            return summarized_count * compression_ratio
        else:
            return 1.0
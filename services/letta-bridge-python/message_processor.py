import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from session_manager import SessionManager
from letta_client import LettaAPIError

logger = logging.getLogger(__name__)

class MessageProcessor:
    """消息处理器 - 处理Redis消息和Letta API之间的转换"""
    
    def __init__(self, redis_client: redis.Redis, session_manager: SessionManager, config: Dict[str, Any]):
        self.redis_client = redis_client
        self.session_manager = session_manager
        self.config = config
        
        # 配置项
        self.input_queue = config.get("redis", {}).get("input_queue", "user_input_queue")
        self.response_channel = config.get("redis", {}).get("response_channel", "letta_responses")
        self.process_memory_types = set(config.get("bridge", {}).get("process_memory_types", ["permanent"]))
        self.fallback_to_memory = config.get("bridge", {}).get("fallback_to_memory", True)
        self.max_concurrent_requests = config.get("bridge", {}).get("max_concurrent_requests", 10)
        
        # 运行时状态
        self.processing_tasks: Dict[str, str] = {}  # task_id -> status
        self.semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        
    async def start_processing(self):
        """开始消息处理主循环"""
        logger.info(f"Starting message processor, listening on queue: {self.input_queue}")
        logger.info(f"Processing memory types: {list(self.process_memory_types)}")
        logger.info(f"Fallback to memory service: {self.fallback_to_memory}")
        
        while True:
            try:
                await self._process_single_message()
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
                await asyncio.sleep(1)  # 避免快速循环
    
    async def _process_single_message(self):
        """处理单条消息"""
        try:
            # 从队列右端弹出消息（FIFO）
            result = await self.redis_client.brpop(self.input_queue, timeout=1)
            
            if not result:
                return  # 超时，继续循环
            
            queue_name, message_data = result
            
            try:
                message = json.loads(message_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in queue message: {e}")
                return
            
            # 异步处理消息
            asyncio.create_task(self._handle_message(message))
            
        except Exception as e:
            logger.error(f"Error processing single message: {e}")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """处理单条消息"""
        task_id = message.get("task_id", "unknown")
        
        # 使用信号量限制并发
        async with self.semaphore:
            try:
                self.processing_tasks[task_id] = "processing"
                logger.info(f"Processing message task_id: {task_id}")
                
                # 检查是否需要永久记忆处理
                if self._should_process_with_letta(message):
                    await self._process_with_letta(message)
                elif self.fallback_to_memory:
                    await self._fallback_to_memory_service(message)
                else:
                    logger.info(f"Skipping task {task_id}: not configured for Letta processing")
                
                self.processing_tasks[task_id] = "completed"
                
            except Exception as e:
                logger.error(f"Error handling message task_id {task_id}: {e}")
                self.processing_tasks[task_id] = "error"
                await self._send_error_response(task_id, str(e))
            finally:
                # 清理任务状态
                self.processing_tasks.pop(task_id, None)
    
    def _should_process_with_letta(self, message: Dict[str, Any]) -> bool:
        """判断消息是否应该用Letta处理"""
        # 检查元数据中的memory_type
        meta = message.get("meta", {})
        if isinstance(meta, dict):
            memory_type = meta.get("memory_type")
            if memory_type in self.process_memory_types:
                return True
        
        # 检查消息类型
        message_type = message.get("type", "")
        if message_type == "text":
            # 对于文本消息，可以根据内容或其他规则判断
            content = message.get("content", "")
            if self._content_indicates_permanent_memory(content):
                return True
        
        return False
    
    def _content_indicates_permanent_memory(self, content: str) -> bool:
        """根据内容判断是否需要永久记忆"""
        # 这里可以实现更复杂的逻辑
        # 例如检测特定关键词、用户意图等
        permanent_keywords = [
            "记住", "记录", "保存", "永久", "长期", "不要忘记",
            "remember", "save", "permanent", "long-term"
        ]
        
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in permanent_keywords)
    
    async def _process_with_letta(self, message: Dict[str, Any]):
        """使用Letta处理消息"""
        task_id = message.get("task_id", "unknown")
        user_id = message.get("user_id", "anonymous")
        content = message.get("content", "")
        
        if not content:
            # 尝试从文件读取内容
            input_file = message.get("input_file")
            if input_file:
                try:
                    with open(input_file, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                except Exception as e:
                    logger.error(f"Failed to read input file {input_file}: {e}")
                    raise
        
        if not content:
            logger.warning(f"No content found for task {task_id}")
            return
        
        logger.info(f"Processing with Letta - user: {user_id}, content: {content[:100]}...")
        
        try:
            # 发送消息到Letta
            letta_response = await self.session_manager.send_message_to_agent(user_id, content)
            
            # 解析Letta响应
            response_content = self._extract_response_content(letta_response)
            
            if not response_content:
                logger.warning(f"Empty response from Letta for task {task_id}")
                response_content = "我正在思考中，请稍等片刻。"
            
            # 发送响应
            await self._send_letta_response(task_id, user_id, response_content, message)
            
            logger.info(f"Letta processing completed for task {task_id}")
            
        except LettaAPIError as e:
            logger.error(f"Letta API error for task {task_id}: {e}")
            if self.fallback_to_memory:
                logger.info(f"Falling back to memory service for task {task_id}")
                await self._fallback_to_memory_service(message)
            else:
                raise
        except Exception as e:
            logger.error(f"Unexpected error in Letta processing for task {task_id}: {e}")
            raise
    
    def _extract_response_content(self, letta_response: Dict[str, Any]) -> str:
        """从Letta响应中提取文本内容"""
        try:
            # Letta API响应格式可能会变化，这里处理常见的格式
            if "messages" in letta_response and isinstance(letta_response["messages"], list):
                # 获取最后一条assistant消息
                for message in reversed(letta_response["messages"]):
                    if message.get("role") == "assistant":
                        return message.get("text", "")
            
            # 直接文本响应
            if "text" in letta_response:
                return letta_response["text"]
            
            # 其他可能的格式
            if "response" in letta_response:
                return letta_response["response"]
            
            # 如果以上都没找到，返回整个响应的字符串形式（调试用）
            logger.warning(f"Unexpected Letta response format: {letta_response}")
            return str(letta_response)
            
        except Exception as e:
            logger.error(f"Error extracting content from Letta response: {e}")
            return ""
    
    async def _send_letta_response(self, task_id: str, user_id: str, content: str, original_message: Dict[str, Any]):
        """发送Letta处理结果"""
        try:
            response_data = {
                "task_id": task_id,
                "user_id": user_id,
                "response_text": content,
                "memory_updated": True,
                "source": "letta",
                "timestamp": asyncio.get_event_loop().time(),
                "original_meta": original_message.get("meta", {})
            }
            
            # 发布到响应频道
            await self.redis_client.publish(
                self.response_channel, 
                json.dumps(response_data, ensure_ascii=False)
            )
            
            logger.info(f"Published Letta response for task {task_id} to channel {self.response_channel}")
            
            # 同时发布到任务特定频道（兼容现有流程）
            task_channel = f"task_response:{task_id}"
            task_response = {
                "text": content,
                "source": "letta"
            }
            
            await self.redis_client.publish(
                task_channel,
                json.dumps(task_response, ensure_ascii=False)
            )
            
            logger.debug(f"Published task response to channel {task_channel}")
            
        except Exception as e:
            logger.error(f"Error sending Letta response for task {task_id}: {e}")
            raise
    
    async def _fallback_to_memory_service(self, message: Dict[str, Any]):
        """回退到原有memory服务处理"""
        task_id = message.get("task_id", "unknown")
        
        try:
            # 重新放回队列，让memory服务处理
            await self.redis_client.lpush(
                self.input_queue, 
                json.dumps(message, ensure_ascii=False)
            )
            
            logger.info(f"Fallback: sent task {task_id} back to memory service")
            
        except Exception as e:
            logger.error(f"Error in fallback for task {task_id}: {e}")
            raise
    
    async def _send_error_response(self, task_id: str, error_message: str):
        """发送错误响应"""
        try:
            error_response = {
                "task_id": task_id,
                "error": True,
                "message": f"Letta bridge error: {error_message}",
                "source": "letta_bridge",
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # 发布错误到响应频道
            await self.redis_client.publish(
                self.response_channel,
                json.dumps(error_response, ensure_ascii=False)
            )
            
            # 同时发送到任务特定频道
            task_channel = f"task_response:{task_id}"
            task_error = {
                "text": f"处理出错: {error_message}",
                "error": True,
                "source": "letta_bridge"
            }
            
            await self.redis_client.publish(
                task_channel,
                json.dumps(task_error, ensure_ascii=False)
            )
            
            logger.error(f"Sent error response for task {task_id}")
            
        except Exception as e:
            logger.error(f"Error sending error response for task {task_id}: {e}")
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        status_counts = {}
        for status in self.processing_tasks.values():
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "active_tasks": len(self.processing_tasks),
            "status_distribution": status_counts,
            "semaphore_available": self.semaphore._value,
            "max_concurrent": self.max_concurrent_requests
        }
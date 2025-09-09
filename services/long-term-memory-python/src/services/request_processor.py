"""
长期记忆请求处理器

负责处理ltm_requests队列中的请求，并将响应发布到ltm_responses频道
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from ..core.redis_client import RedisMessageBus
from ..models.memory import MemorySearchResult


class LTMRequestProcessor:
    """长期记忆请求处理器"""
    
    def __init__(self, redis_client: RedisMessageBus, mem0_client, profile_service):
        self.redis_client = redis_client
        self.mem0_client = mem0_client 
        self.profile_service = profile_service
        self.logger = logging.getLogger(__name__)
        self._running = False

    async def start_consuming(self, max_workers: int = 3):
        """
        开始消费ltm_requests队列，支持并发处理
        
        Args:
            max_workers: 最大并发工作者数量
        """
        self._running = True
        self.logger.info(f"开始监听ltm_requests队列，并发工作者数: {max_workers}")
        
        # 创建并发工作者
        workers = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(max_workers)
        ]
        
        try:
            # 等待所有工作者完成
            await asyncio.gather(*workers, return_exceptions=True)
        finally:
            # 确保所有任务被清理
            for worker in workers:
                if not worker.done():
                    worker.cancel()

    async def _worker_loop(self, worker_id: int):
        """工作者循环"""
        self.logger.info(f"工作者 {worker_id} 启动")
        
        while self._running:
            try:
                await self._consume_single_message()
            except Exception as e:
                self.logger.error(f"工作者 {worker_id} 处理消息时发生错误: {e}")
                await asyncio.sleep(1)  # 错误后短暂暂停
                
        self.logger.info(f"工作者 {worker_id} 停止")

    async def stop_consuming(self):
        """停止消费队列"""
        self._running = False
        self.logger.info("停止监听ltm_requests队列")

    async def _consume_single_message(self):
        """消费单条消息（用于测试和工作者循环）"""
        try:
            # 阻塞式获取队列消息，超时1秒
            result = await self.redis_client.brpop(["ltm_requests"], timeout=1)
            
            if result:
                queue_name, message_data = result
                
                # 解析请求数据，支持重试
                request = await self._parse_request_with_retry(message_data)
                if not request:
                    return
                
                self.logger.info(f"收到请求: {request.get('request_id')}, 类型: {request.get('type')}")
                
                # 处理请求
                response = await self._process_request_with_retry(request)
                
                # 发布响应
                await self._publish_response_with_retry(response)
                
                self.logger.info(f"请求处理完成: {request.get('request_id')}")
                
        except Exception as e:
            self.logger.error(f"消费消息时发生未捕获的错误: {e}")

    async def _parse_request_with_retry(self, message_data: str, max_retries: int = 3) -> Optional[Dict[str, Any]]:
        """带重试的请求解析"""
        for attempt in range(max_retries):
            try:
                return json.loads(message_data)
            except json.JSONDecodeError as e:
                self.logger.warning(f"解析请求数据失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"请求数据解析失败，已达到最大重试次数: {message_data[:100]}...")
                    return None
                await asyncio.sleep(0.1)  # 短暂延迟后重试
        
        return None

    async def _process_request_with_retry(self, request: Dict[str, Any], max_retries: int = 2) -> Dict[str, Any]:
        """带重试的请求处理"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self.process_request(request)
            except Exception as e:
                last_error = e
                self.logger.warning(f"处理请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # 指数退避
        
        # 所有重试都失败，返回错误响应
        return self._create_error_response(
            request.get("request_id"),
            f"处理请求失败，已达到最大重试次数: {str(last_error)}"
        )

    async def _publish_response_with_retry(self, response: Dict[str, Any], max_retries: int = 3):
        """带重试的响应发布"""
        for attempt in range(max_retries):
            try:
                await self.redis_client.publish("ltm_responses", json.dumps(response))
                return
            except Exception as e:
                self.logger.warning(f"发布响应失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    self.logger.error(f"响应发布失败，已达到最大重试次数: {response.get('request_id')}")
                    raise
                await asyncio.sleep(0.2 * (attempt + 1))  # 指数退避

    async def process_request(self, request: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        """
        处理单个请求，支持超时控制
        
        Args:
            request: 请求数据
            timeout: 请求超时时间（秒）
            
        Returns:
            响应数据
        """
        try:
            # 验证请求格式
            validation_error = self._validate_request(request)
            if validation_error:
                return self._create_error_response(request.get("request_id"), validation_error)
            
            request_type = request["type"]
            request_id = request["request_id"]
            
            # 使用超时控制处理请求
            try:
                # 根据请求类型分发处理，加上超时控制
                if request_type == "search":
                    return await asyncio.wait_for(
                        self._handle_search_request(request), 
                        timeout=timeout
                    )
                elif request_type == "add_memory":
                    return await asyncio.wait_for(
                        self._handle_add_memory_request(request), 
                        timeout=timeout
                    )
                elif request_type == "profile_get":
                    return await asyncio.wait_for(
                        self._handle_profile_get_request(request), 
                        timeout=timeout
                    )
                else:
                    return self._create_error_response(request_id, f"不支持的请求类型: {request_type}")
                    
            except asyncio.TimeoutError:
                self.logger.error(f"请求处理超时: {request_id}")
                return self._create_error_response(request_id, f"请求处理超时（{timeout}秒）")
                
        except Exception as e:
            self.logger.error(f"处理请求时发生错误: {e}")
            return self._create_error_response(
                request.get("request_id"), 
                f"内部处理错误: {str(e)}"
            )

    def _validate_request(self, request: Dict[str, Any]) -> Optional[str]:
        """验证请求格式"""
        required_fields = ["request_id", "type", "user_id", "data"]
        
        for field in required_fields:
            if field not in request:
                return f"缺少必要字段: {field}"
                
        return None

    async def _handle_search_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理搜索记忆请求"""
        try:
            user_id = request["user_id"]
            request_id = request["request_id"]
            search_data = request["data"]
            
            query = search_data.get("query", "")
            limit = search_data.get("limit", 10)
            
            # 使用Mem0客户端搜索记忆
            memories = await self.mem0_client.search(
                query=query,
                user_id=user_id,
                limit=limit
            )
            
            # 格式化搜索结果
            formatted_memories = []
            for memory in memories:
                formatted_memory = {
                    "id": memory.get("id"),
                    "memory": memory.get("memory"),
                    "score": memory.get("score", 0.0),
                    "metadata": memory.get("metadata", {})
                }
                formatted_memories.append(formatted_memory)
            
            return {
                "request_id": request_id,
                "status": "success",
                "memories": formatted_memories,
                "total_count": len(formatted_memories),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return self._create_error_response(request["request_id"], str(e))

    async def _handle_add_memory_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理添加记忆请求"""
        try:
            user_id = request["user_id"]
            request_id = request["request_id"] 
            add_data = request["data"]
            
            content = add_data.get("content", "")
            metadata = add_data.get("metadata", {})
            
            # 使用Mem0客户端添加记忆
            memory_id = await self.mem0_client.add(
                messages=content,
                user_id=user_id,
                metadata=metadata
            )
            
            return {
                "request_id": request_id,
                "status": "success", 
                "memory_id": memory_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return self._create_error_response(request["request_id"], str(e))

    async def _handle_profile_get_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理获取用户画像请求"""
        try:
            user_id = request["user_id"]
            request_id = request["request_id"]
            
            # 获取用户画像
            user_profile = await self.profile_service.get_user_profile(user_id)
            
            return {
                "request_id": request_id,
                "status": "success",
                "user_profile": user_profile,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return self._create_error_response(request["request_id"], str(e))

    def _create_error_response(self, request_id: Optional[str], error_message: str) -> Dict[str, Any]:
        """创建错误响应"""
        return {
            "request_id": request_id,
            "status": "error",
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        }


class RequestProcessorManager:
    """请求处理器管理器"""
    
    def __init__(self, redis_client: RedisMessageBus, mem0_client, profile_service):
        self.processor = LTMRequestProcessor(redis_client, mem0_client, profile_service)
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """启动请求处理器"""
        self.logger.info("启动长期记忆请求处理器...")
        await self.processor.start_consuming()

    async def stop(self):
        """停止请求处理器"""
        self.logger.info("停止长期记忆请求处理器...")
        await self.processor.stop_consuming()
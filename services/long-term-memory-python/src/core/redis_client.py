"""
Redis消息总线客户端 - TDD循环1重构优化版本

重构改进：
1. 改进连接管理和资源清理
2. 增强错误处理和重试机制
3. 提取消息序列化/反序列化逻辑
4. 优化配置验证和类型安全
5. 改进日志记录和监控
"""
import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
from redis.exceptions import ConnectionError, TimeoutError, RedisError
from pydantic import BaseModel, ValidationError

from src.models.messages import MemoryUpdateMessage, LTMRequest, LTMResponse


class MessageType(Enum):
    """消息类型枚举"""
    MEMORY_UPDATE = "memory_update"
    LTM_REQUEST = "ltm_request"
    LTM_RESPONSE = "ltm_response"


@dataclass
class RedisConfig:
    """Redis配置数据类"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    socket_connect_timeout: int = 10
    socket_timeout: int = 10
    retry_on_timeout: bool = True
    max_connections: int = 10
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'RedisConfig':
        """从字典创建配置实例"""
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})


class MessageSerializationError(Exception):
    """消息序列化异常"""
    pass


class RedisMessageBus:
    """Redis消息总线，处理订阅/发布和队列操作
    
    重构改进：
    - 使用连接池优化性能
    - 增强错误处理和重试机制
    - 改进资源管理
    - 提取消息处理逻辑
    """
    
    def __init__(self, redis_config: Union[Dict[str, Any], RedisConfig]):
        if isinstance(redis_config, dict):
            self.config = RedisConfig.from_dict(redis_config)
        else:
            self.config = redis_config
            
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub_client: Optional[redis.Redis] = None
        self.connection_pool: Optional[redis.ConnectionPool] = None
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._message_handlers = {
            MessageType.MEMORY_UPDATE: self._deserialize_memory_update,
            MessageType.LTM_REQUEST: self._deserialize_ltm_request,
            MessageType.LTM_RESPONSE: self._serialize_ltm_response
        }
    
    def _deserialize_memory_update(self, data: str) -> MemoryUpdateMessage:
        """反序列化memory update消息"""
        try:
            message_data = json.loads(data)
            return MemoryUpdateMessage(**message_data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise MessageSerializationError(f"反序列化memory update失败: {e}")
    
    def _deserialize_ltm_request(self, data: str) -> LTMRequest:
        """反序列化LTM请求消息"""
        try:
            message_data = json.loads(data)
            return LTMRequest(**message_data)
        except (json.JSONDecodeError, ValidationError) as e:
            raise MessageSerializationError(f"反序列化LTM请求失败: {e}")
    
    def _serialize_ltm_response(self, response: LTMResponse) -> str:
        """序列化LTM响应消息"""
        try:
            return response.model_dump_json()
        except Exception as e:
            raise MessageSerializationError(f"序列化LTM响应失败: {e}")
    
    async def connect(self) -> None:
        """建立Redis连接
        
        重构改进：
        - 使用连接池提高性能
        - 改进错误处理和重试逻辑
        - 更详细的连接状态日志
        """
        try:
            # 创建连接池
            self.connection_pool = redis.ConnectionPool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                decode_responses=True,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_timeout=self.config.socket_timeout,
                retry_on_timeout=self.config.retry_on_timeout,
                max_connections=self.config.max_connections
            )
            
            # 创建Redis客户端使用连接池
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # 创建独立的pub/sub客户端
            self.pubsub_client = redis.Redis(
                host=self.config.host,
                port=self.config.port,
                db=self.config.db,
                decode_responses=True,
                socket_connect_timeout=self.config.socket_connect_timeout,
                socket_timeout=self.config.socket_timeout
            )
            
            # 测试连接
            await self.check_connection()
            self.logger.info(
                f"Redis连接建立成功 - {self.config.host}:{self.config.port}/{self.config.db}"
            )
            
        except Exception as e:
            self.logger.error(f"Redis连接失败: {e}")
            await self._cleanup_connections()
            raise
    
    async def check_connection(self) -> bool:
        """检查Redis连接状态"""
        try:
            await self.redis_client.ping()
            return True
        except Exception as e:
            self.logger.error(f"Redis连接检查失败: {e}")
            raise
    
    async def disconnect(self) -> None:
        """关闭Redis连接
        
        重构改进：
        - 更安全的任务取消机制
        - 改进资源清理流程
        - 增加超时保护
        """
        self._running = False
        
        # 取消并等待所有任务完成（带超时保护）
        if self._tasks:
            # 取消所有任务
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            
            # 等待任务完成，最多等待5秒
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                self.logger.warning("任务取消超时，强制清理")
            
            self._tasks.clear()
        
        # 清理连接
        await self._cleanup_connections()
        self.logger.info("Redis连接已关闭")
    
    async def _cleanup_connections(self) -> None:
        """清理Redis连接资源"""
        try:
            if self.redis_client:
                await self.redis_client.close()
            
            if self.pubsub_client:
                await self.pubsub_client.close()
                
            if self.connection_pool:
                await self.connection_pool.disconnect()
                
        except Exception as e:
            self.logger.error(f"清理连接资源时出错: {e}")
    
    async def subscribe_memory_updates(
        self, 
        handler: Callable[[MemoryUpdateMessage], None],
        channel: str = "memory_updates"
    ) -> None:
        """订阅memory_updates频道"""
        if not self.pubsub_client:
            raise RuntimeError("Redis客户端未连接")
        
        pubsub = self.pubsub_client.pubsub()
        await pubsub.subscribe(channel)
        
        self.logger.info(f"开始监听频道: {channel}")
        self._running = True
        
        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                    
                if message["type"] == "message":
                    try:
                        memory_message = self._deserialize_memory_update(message["data"])
                        await handler(memory_message)
                        
                    except MessageSerializationError as e:
                        self.logger.error(f"解析memory_updates消息失败: {e}")
                    except Exception as e:
                        self.logger.error(f"处理memory_updates消息失败: {e}")
                        
        except Exception as e:
            self.logger.error(f"订阅memory_updates失败: {e}")
            raise
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
    
    async def process_ltm_requests(
        self,
        handler: Callable[[LTMRequest], LTMResponse],
        queue: str = "ltm_requests",
        timeout: int = 5
    ) -> None:
        """处理ltm_requests队列"""
        if not self.redis_client:
            raise RuntimeError("Redis客户端未连接")
        
        self.logger.info(f"开始处理队列: {queue}")
        self._running = True
        
        try:
            while self._running:
                try:
                    # 阻塞式弹出队列消息
                    result = await self.redis_client.brpop(queue, timeout=timeout)
                    
                    if result:
                        queue_name, message_data = result
                        
                        try:
                            request = self._deserialize_ltm_request(message_data)
                            
                            # 处理请求
                            response = await handler(request)
                            
                            # 发布响应
                            await self.publish_ltm_response(response)
                            
                        except MessageSerializationError as e:
                            self.logger.error(f"解析LTM请求失败: {e}")
                        except Exception as e:
                            self.logger.error(f"处理LTM请求失败: {e}")
                            # 尝试从原始数据提取基本信息用于错误响应
                            try:
                                raw_data = json.loads(message_data)
                                error_response = LTMResponse(
                                    request_id=raw_data.get("request_id", "unknown"),
                                    user_id=raw_data.get("user_id", "unknown"),
                                    success=False,
                                    error=str(e)
                                )
                                await self.publish_ltm_response(error_response)
                            except Exception:
                                self.logger.error("无法发送错误响应")
                
                except asyncio.TimeoutError:
                    # 正常超时，继续循环
                    continue
                except Exception as e:
                    self.logger.error(f"处理队列消息失败: {e}")
                    await asyncio.sleep(1)  # 避免快速重试
                    
        except Exception as e:
            self.logger.error(f"队列处理失败: {e}")
            raise
    
    async def publish_ltm_response(
        self, 
        response: LTMResponse, 
        channel: str = "ltm_responses"
    ) -> None:
        """发布ltm_responses消息"""
        if not self.redis_client:
            raise RuntimeError("Redis客户端未连接")
        
        try:
            # 序列化响应
            response_data = self._serialize_ltm_response(response)
            
            # 发布到频道
            await self.redis_client.publish(channel, response_data)
            
            self.logger.debug(f"LTM响应已发布: {response.request_id}")
            
        except Exception as e:
            self.logger.error(f"发布LTM响应失败: {e}")
            raise
    
    async def start_background_tasks(
        self,
        memory_handler: Callable[[MemoryUpdateMessage], None],
        request_handler: Callable[[LTMRequest], LTMResponse]
    ) -> None:
        """启动后台任务"""
        if not self._running:
            self._running = True
            
            # 启动memory_updates订阅任务
            memory_task = asyncio.create_task(
                self.subscribe_memory_updates(memory_handler)
            )
            self._tasks.append(memory_task)
            
            # 启动ltm_requests处理任务
            request_task = asyncio.create_task(
                self.process_ltm_requests(request_handler)
            )
            self._tasks.append(request_task)
            
            self.logger.info("后台任务已启动")
    
    async def stop_background_tasks(self) -> None:
        """停止后台任务"""
        self._running = False
        self.logger.info("正在停止后台任务...")
        await self.disconnect()


@asynccontextmanager
async def get_redis_message_bus(config: Dict[str, Any]):
    """Redis消息总线上下文管理器"""
    bus = RedisMessageBus(config)
    try:
        await bus.connect()
        yield bus
    finally:
        await bus.disconnect()
"""
消息处理服务

负责处理memory_updates消息，协调各组件完成记忆存储流程
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.mem0_client import Mem0Service


class MessageProcessor:
    """消息处理器 - 处理memory_updates消息"""
    
    def __init__(self, redis_client, mem0_client):
        self.redis_client = redis_client
        self.mem0_client = mem0_client
        self.logger = logging.getLogger(__name__)

    async def process_memory_update(self, memory_update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理memory_updates消息
        
        Args:
            memory_update: 记忆更新消息
            
        Returns:
            处理结果，包含memory_id等信息
        """
        try:
            # 验证消息格式
            if not self._validate_message_format(memory_update):
                self.logger.error("消息格式无效")
                return {"error": "invalid_message_format"}
            
            user_id = memory_update["user_id"]
            content = memory_update["content"]
            metadata = {
                "source": memory_update.get("source", "unknown"),
                "timestamp": memory_update.get("timestamp", datetime.now().timestamp()),
                "session_id": memory_update.get("meta", {}).get("session_id")
            }
            
            # 使用Mem0存储记忆
            memory_id = await self.mem0_client.add(
                messages=content,
                user_id=user_id,
                metadata=metadata
            )
            
            self.logger.info(f"记忆已存储: {memory_id}")
            
            return {
                "memory_id": memory_id,
                "user_id": user_id,
                "status": "success"
            }
            
        except Exception as e:
            self.logger.error(f"处理记忆更新失败: {e}")
            return {"error": str(e)}

    async def start_memory_updates_subscription(self):
        """启动memory_updates订阅处理"""
        try:
            pubsub = await self.redis_client.pubsub()
            await pubsub.subscribe("memory_updates")
            
            self.logger.info("开始订阅memory_updates频道")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        memory_update = json.loads(message["data"])
                        await self.process_memory_update(memory_update)
                    except json.JSONDecodeError:
                        self.logger.error("消息JSON解析失败")
                    except Exception as e:
                        self.logger.error(f"处理订阅消息失败: {e}")
                        
        except Exception as e:
            self.logger.error(f"订阅处理失败: {e}")

    def _validate_message_format(self, message: Dict[str, Any]) -> bool:
        """验证消息格式"""
        required_fields = ["user_id", "content"]
        return all(field in message and message[field] for field in required_fields)
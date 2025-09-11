"""
长期记忆服务入口点
"""
import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any, Dict

import redis.asyncio as redis

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.config_loader import config_loader
from src.core.mem0_client import Mem0Service


async def _init_redis() -> redis.Redis:
    conf = config_loader.get_redis_config()
    client = redis.Redis(
        host=conf.get("host", os.getenv("REDIS_HOST", "localhost")),
        port=conf.get("port", int(os.getenv("REDIS_PORT", 6379))),
        db=conf.get("db", 0),
        decode_responses=True,
    )
    await client.ping()
    return client


async def _handle_memory_updates(redis_client: redis.Redis, mem0: Mem0Service, channel_name: str):
    logger = logging.getLogger(__name__)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)
    logger.info(f"LTM subscribed to channel: {channel_name}")
    async for message in pubsub.listen():
        if message.get("type") != "message":
            continue
        try:
            data = json.loads(message.get("data"))
            user_id = data.get("user_id")
            content = data.get("content")
            if not user_id or not content:
                continue
            metadata = {
                "source": data.get("source"),
                "timestamp": data.get("timestamp"),
                "session_id": (data.get("meta") or {}).get("session_id") if isinstance(data.get("meta"), dict) else None,
            }
            await mem0.add_memory({"user_id": user_id, "content": content, "metadata": metadata})
        except Exception as e:
            logger.error(f"Failed to index memory update: {e}")


async def _handle_ltm_requests(redis_client: redis.Redis, mem0: Mem0Service, queue_name: str, resp_channel: str):
    logger = logging.getLogger(__name__)
    logger.info(f"LTM consuming queue: {queue_name}, responding on: {resp_channel}")
    while True:
        try:
            item = await redis_client.brpop(queue_name, timeout=1)
            if not item:
                continue
            _q, raw = item
            try:
                req = json.loads(raw)
            except Exception:
                logger.warning("Invalid JSON in ltm_requests, skipping")
                continue

            request_id = req.get("request_id")
            user_id = req.get("user_id")
            rtype = req.get("type")
            data = req.get("data") or {}

            resp: Dict[str, Any] = {"request_id": request_id, "user_id": user_id, "success": True}
            try:
                if rtype == "search":
                    query = data.get("query", "")
                    limit = int((data.get("limit") or 5))
                    memories = await mem0.search(query=query, user_id=user_id, limit=limit)
                    resp["memories"] = memories
                elif rtype == "add":
                    content = data.get("content", "")
                    metadata = data.get("metadata") or {}
                    mid = await mem0.add_memory({"user_id": user_id, "content": content, "metadata": metadata})
                    resp["memories"] = [{"id": mid, "content": content}]
                elif rtype == "profile_get":
                    # Placeholder: return empty profile until implemented
                    resp["user_profile"] = {}
                elif rtype == "profile_update":
                    resp["user_profile"] = data.get("updates") or {}
                else:
                    resp.update({"success": False, "error": f"unknown_request_type:{rtype}"})
            except Exception as e:
                resp.update({"success": False, "error": str(e)})

            # publish response
            await redis_client.publish(resp_channel, json.dumps(resp, ensure_ascii=False))
        except Exception as e:
            logger.error(f"LTM request loop error: {e}")
            await asyncio.sleep(0.1)


async def main():
    """主函数"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("启动长期记忆服务...")
    
    try:
        # 初始化组件
        redis_client = await _init_redis()
        mem0 = Mem0Service(config_loader.get_mem0_config())

        channels = config_loader.get_channels_config()
        queues = config_loader.get_queues_config()
        memory_updates_ch = channels.get("memory_updates", "memory_updates")
        ltm_responses_ch = channels.get("ltm_responses", "ltm_responses")
        ltm_requests_q = queues.get("ltm_requests", "ltm_requests")

        logger.info("服务初始化完成，开始监听消息…")

        await asyncio.gather(
            _handle_memory_updates(redis_client, mem0, memory_updates_ch),
            _handle_ltm_requests(redis_client, mem0, ltm_requests_q, ltm_responses_ch),
        )
            
    except KeyboardInterrupt:
        logger.info("接收到停止信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务运行异常: {e}")
        raise
    finally:
        logger.info("服务已关闭")


if __name__ == "__main__":
    # 处理信号
    def signal_handler(signum, frame):
        print("\n接收到终止信号，正在关闭...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 运行服务
    asyncio.run(main())

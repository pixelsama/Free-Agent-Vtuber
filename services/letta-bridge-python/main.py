import asyncio
import json
import logging
import os
import signal
from pathlib import Path
from typing import Optional

import redis.asyncio as redis
from letta_client import LettaClient, LettaClientPool
from session_manager import SessionManager
from message_processor import MessageProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client: Optional[redis.Redis] = None
letta_client: Optional[LettaClient] = None
letta_client_pool: Optional[LettaClientPool] = None
session_manager: Optional[SessionManager] = None
message_processor: Optional[MessageProcessor] = None
config = {}
shutdown_event = asyncio.Event()

def load_config():
    """加载配置文件"""
    global config
    try:
        config_path = Path(__file__).parent / "config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 环境变量覆盖配置
        if os.getenv("REDIS_HOST"):
            config["redis"]["host"] = os.getenv("REDIS_HOST")
        if os.getenv("REDIS_PORT"):
            config["redis"]["port"] = int(os.getenv("REDIS_PORT"))
        if os.getenv("LETTA_API_URL"):
            config["letta"]["api_url"] = os.getenv("LETTA_API_URL")
        if os.getenv("LETTA_API_KEY"):
            config["letta"]["api_key"] = os.getenv("LETTA_API_KEY")
        
        logger.info("Configuration loaded successfully")
        logger.info(f"Redis: {config['redis']['host']}:{config['redis']['port']}")
        logger.info(f"Letta API: {config['letta']['api_url']}")
        return True
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return False

async def init_redis():
    """初始化Redis连接"""
    global redis_client
    try:
        redis_config = config.get("redis", {})
        redis_host = redis_config.get("host", "localhost")
        redis_port = redis_config.get("port", 6379)

        redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True
        )
        await redis_client.ping()
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        redis_client = None
        return False

async def init_letta():
    """初始化Letta客户端和连接池"""
    global letta_client, letta_client_pool
    try:
        letta_config = config.get("letta", {})
        api_url = letta_config.get("api_url", "http://localhost:8283")
        api_key = letta_config.get("api_key")
        timeout = letta_config.get("timeout", 30)
        max_retries = letta_config.get("retry_attempts", 3)
        
        # 创建主要的Letta客户端
        letta_client = LettaClient(
            base_url=api_url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries
        )
        
        # 测试连接
        async with letta_client:
            health_ok = await letta_client.health_check()
            if not health_ok:
                raise Exception("Letta health check failed")
        
        # 创建连接池（用于高并发场景）
        bridge_config = config.get("bridge", {})
        pool_size = bridge_config.get("max_concurrent_requests", 10)
        
        letta_client_pool = LettaClientPool(
            base_url=api_url,
            api_key=api_key,
            pool_size=pool_size,
            timeout=timeout,
            max_retries=max_retries
        )
        
        logger.info(f"Letta client initialized successfully: {api_url}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize Letta client: {e}")
        letta_client = None
        letta_client_pool = None
        return False

async def init_components():
    """初始化各个组件"""
    global session_manager, message_processor
    
    if not redis_client or not letta_client:
        logger.error("Cannot initialize components without Redis and Letta clients")
        return False
    
    try:
        # 初始化会话管理器
        session_manager = SessionManager(redis_client, letta_client, config)
        logger.info("Session manager initialized")
        
        # 初始化消息处理器
        message_processor = MessageProcessor(redis_client, session_manager, config)
        logger.info("Message processor initialized")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        return False

async def cleanup():
    """清理资源"""
    logger.info("Starting cleanup...")
    
    # 关闭Letta连接
    if letta_client:
        try:
            await letta_client.close()
        except Exception as e:
            logger.error(f"Error closing Letta client: {e}")
    
    if letta_client_pool:
        try:
            await letta_client_pool.close_all()
        except Exception as e:
            logger.error(f"Error closing Letta client pool: {e}")
    
    # 关闭Redis连接
    if redis_client:
        try:
            await redis_client.close()
        except Exception as e:
            logger.error(f"Error closing Redis client: {e}")
    
    logger.info("Letta Bridge Service shutdown complete")

async def health_check_task():
    """健康检查任务"""
    while not shutdown_event.is_set():
        try:
            # 等待30分钟或shutdown事件
            await asyncio.wait_for(shutdown_event.wait(), timeout=1800)
        except asyncio.TimeoutError:
            # 超时是正常的，执行健康检查
            try:
                if redis_client:
                    await redis_client.ping()
                
                if letta_client:
                    async with letta_client:
                        await letta_client.health_check()
                
                logger.debug("Health check passed")
                
            except Exception as e:
                logger.warning(f"Health check failed: {e}")

async def session_cleanup_task():
    """定期清理过期会话"""
    while not shutdown_event.is_set():
        try:
            # 等待1小时或shutdown事件
            await asyncio.wait_for(shutdown_event.wait(), timeout=3600)
        except asyncio.TimeoutError:
            # 超时是正常的，执行清理
            if session_manager:
                try:
                    await session_manager.cleanup_expired_sessions()
                except Exception as e:
                    logger.error(f"Session cleanup error: {e}")

async def stats_task():
    """定期输出统计信息"""
    while not shutdown_event.is_set():
        try:
            # 等待10分钟或shutdown事件
            await asyncio.wait_for(shutdown_event.wait(), timeout=600)
        except asyncio.TimeoutError:
            # 输出统计信息
            try:
                if message_processor:
                    proc_stats = message_processor.get_processing_stats()
                    logger.info(f"Processing stats: {proc_stats}")
                
                if session_manager:
                    session_stats = await session_manager.get_session_stats()
                    logger.info(f"Session stats: {session_stats}")
                    
            except Exception as e:
                logger.error(f"Stats collection error: {e}")

def setup_signal_handlers():
    """设置信号处理器"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, initiating shutdown...")
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """主函数"""
    logger.info("Starting Letta Bridge Service...")
    
    # 设置信号处理
    setup_signal_handlers()
    
    try:
        # 加载配置
        if not load_config():
            logger.error("Failed to load configuration, exiting")
            return
        
        # 初始化Redis
        if not await init_redis():
            logger.error("Failed to initialize Redis, exiting")
            return
        
        # 初始化Letta
        if not await init_letta():
            logger.error("Failed to initialize Letta, exiting")
            return
        
        # 初始化组件
        if not await init_components():
            logger.error("Failed to initialize components, exiting")
            return
        
        logger.info("All components initialized successfully")
        logger.info(f"Listening on queue: {config.get('redis', {}).get('input_queue', 'user_input_queue')}")
        logger.info(f"Publishing to channel: {config.get('redis', {}).get('response_channel', 'letta_responses')}")
        
        # 启动所有任务
        tasks = [
            asyncio.create_task(message_processor.start_processing(), name="message_processor"),
            asyncio.create_task(health_check_task(), name="health_check"),
            asyncio.create_task(session_cleanup_task(), name="session_cleanup"),
            asyncio.create_task(stats_task(), name="stats")
        ]
        
        logger.info("Letta Bridge Service is running...")
        
        # 等待shutdown事件或任务完成
        done, pending = await asyncio.wait(
            tasks + [asyncio.create_task(shutdown_event.wait())],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # 取消未完成的任务
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
    finally:
        await cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service crashed: {e}")
        exit(1)
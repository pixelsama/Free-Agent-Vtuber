"""
长期记忆服务入口点
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.utils.config_loader import config_loader


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
        # TODO: 初始化各种组件
        # - Redis客户端
        # - Mem0客户端
        # - Qdrant客户端
        # - 消息处理器
        logger.info("服务初始化完成")
        
        # TODO: 启动消息监听和处理
        logger.info("开始监听消息...")
        
        # 保持服务运行
        while True:
            await asyncio.sleep(1)
            
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
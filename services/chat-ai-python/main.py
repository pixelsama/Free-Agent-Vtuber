import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import redis.asyncio as redis

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client: Optional[redis.Redis] = None
processing_tasks = {}

class AIProcessor:
    def __init__(self):
        self.model_name = "简单回复模型"
        
    async def process_text(self, text: str) -> str:
        """处理文本输入，返回AI回复"""
        try:
            # 这里实现简单的回复逻辑
            # 在实际项目中，这里会调用OpenAI、Claude等API
            
            text = text.strip().lower()
            
            # 简单的规则回复
            if "你好" in text or "hello" in text:
                return "你好！我是AI虚拟主播，很高兴见到你！"
            elif "天气" in text:
                return "今天天气不错呢！不过我建议你查看天气预报获取准确信息。"
            elif "唱歌" in text:
                return "我很想为你唱歌，但目前还在学习中。不过我可以和你聊天！"
            elif "再见" in text or "拜拜" in text:
                return "再见！期待下次和你聊天，记得常来找我哦！"
            elif "谢谢" in text:
                return "不用谢！能帮到你我很开心。还有什么想聊的吗？"
            elif "?" in text or "？" in text:
                return f"关于「{text.replace('?', '').replace('？', '')}」这个问题，让我想想... 这确实是个有趣的话题呢！"
            else:
                return f"你说「{text}」，这很有意思！作为AI主播，我正在学习如何更好地与大家交流。"
                
        except Exception as e:
            logger.error(f"Error processing text: {e}")
            return "抱歉，我遇到了一些技术问题。请稍后再试！"
    
    async def process_audio(self, audio_file: str) -> tuple[str, Optional[str]]:
        """处理音频输入，返回文本回复和音频文件路径"""
        try:
            # 这里应该实现语音识别
            # 目前返回模拟结果
            logger.info(f"Processing audio file: {audio_file}")
            
            # 模拟语音识别结果
            recognized_text = "你好，我刚才说了一些话"
            
            # 处理识别出的文本
            response_text = await self.process_text(recognized_text)
            
            # 这里应该调用TTS生成音频回复
            # 目前返回None表示没有音频
            response_audio = None
            
            return response_text, response_audio
            
        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            return "抱歉，音频处理出现问题。", None

class TaskProcessor:
    def __init__(self):
        self.ai_processor = AIProcessor()
        
    async def process_task(self, task_data: dict):
        """处理单个任务"""
        try:
            task_id = task_data["task_id"]
            task_type = task_data["type"]
            input_file = task_data["input_file"]
            
            logger.info(f"Processing task {task_id}, type: {task_type}")
            processing_tasks[task_id] = "processing"
            
            if task_type == "text":
                await self._process_text_task(task_id, input_file)
            elif task_type == "audio":
                await self._process_audio_task(task_id, input_file)
            else:
                logger.warning(f"Unknown task type: {task_type}")
                await self._send_error_response(task_id, f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(f"Error processing task: {e}")
            task_id = task_data.get("task_id", "unknown")
            await self._send_error_response(task_id, str(e))
        finally:
            if task_id in processing_tasks:
                del processing_tasks[task_id]
    
    async def _process_text_task(self, task_id: str, input_file: str):
        """处理文本任务"""
        try:
            # 读取输入文本
            with open(input_file, "r", encoding="utf-8") as f:
                input_text = f.read().strip()
            
            logger.info(f"Input text: {input_text[:100]}...")
            
            # AI处理
            response_text = await self.ai_processor.process_text(input_text)
            
            # 发送响应
            await self._send_response(task_id, response_text, None)
            
        except Exception as e:
            logger.error(f"Error in text task {task_id}: {e}")
            await self._send_error_response(task_id, str(e))
    
    async def _process_audio_task(self, task_id: str, input_file: str):
        """处理音频任务"""
        try:
            # AI处理音频
            response_text, response_audio = await self.ai_processor.process_audio(input_file)
            
            # 发送响应
            await self._send_response(task_id, response_text, response_audio)
            
        except Exception as e:
            logger.error(f"Error in audio task {task_id}: {e}")
            await self._send_error_response(task_id, str(e))
    
    async def _send_response(self, task_id: str, text: str, audio_file: Optional[str]):
        """发送处理结果到Redis响应频道"""
        if not redis_client:
            logger.error("Redis client not available")
            return
            
        try:
            response = {
                "text": text,
            }
            
            if audio_file:
                response["audio_file"] = audio_file
            
            # 发送到特定任务的响应频道
            channel = f"task_response:{task_id}"
            await redis_client.publish(channel, json.dumps(response))
            
            logger.info(f"Sent response for task {task_id} to channel {channel}")
            processing_tasks[task_id] = "completed"
            
        except Exception as e:
            logger.error(f"Error sending response for task {task_id}: {e}")
    
    async def _send_error_response(self, task_id: str, error_message: str):
        """发送错误响应"""
        if not redis_client:
            return
            
        try:
            response = {
                "text": f"处理出错: {error_message}",
                "error": True
            }
            
            channel = f"task_response:{task_id}"
            await redis_client.publish(channel, json.dumps(response))
            
            logger.error(f"Sent error response for task {task_id}: {error_message}")
            processing_tasks[task_id] = "error"
            
        except Exception as e:
            logger.error(f"Error sending error response: {e}")

async def init_redis():
    global redis_client
    try:
        redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        await redis_client.ping()
        logger.info("Connected to Redis")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        redis_client = None

async def cleanup_redis():
    if redis_client:
        await redis_client.close()
    logger.info("AI Processor shutdown")

async def queue_listener():
    """监听Redis输入队列"""
    if not redis_client:
        logger.error("Redis client not available")
        return
        
    processor = TaskProcessor()
    
    logger.info("Starting queue listener for user_input_queue")
    
    while True:
        try:
            # 从队列中获取任务 (阻塞式)
            result = await redis_client.brpop("user_input_queue", timeout=1)
            
            if result:
                queue_name, message = result
                task_data = json.loads(message)
                
                logger.info(f"Received task: {task_data}")
                
                # 异步处理任务
                asyncio.create_task(processor.process_task(task_data))
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in queue message: {e}")
        except Exception as e:
            logger.error(f"Error in queue listener: {e}")
            await asyncio.sleep(1)  # 出错时等待1秒

async def main():
    """主函数"""
    logger.info("Starting AI Chat Processor...")
    
    # 初始化Redis
    await init_redis()
    
    if not redis_client:
        logger.error("Cannot start without Redis connection")
        return
    
    try:
        # 启动队列监听器
        await queue_listener()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await cleanup_redis()

if __name__ == "__main__":
    asyncio.run(main())
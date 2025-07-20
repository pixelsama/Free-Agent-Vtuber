import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG级别以便更好调试
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client: Optional[redis.Redis] = None
active_connections: Dict[str, WebSocket] = {}
task_status: Dict[str, str] = {}

async def init_redis():
    global redis_client
    try:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        await redis_client.ping()
        logger.info(f"Connected to Redis at {redis_host}:{redis_port}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        redis_client = None

async def cleanup_redis():
    if redis_client:
        await redis_client.close()
    logger.info("Output Handler shutdown")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await init_redis()
    logger.info("Output Handler started - ready to send results")
    yield
    # 关闭时执行
    await cleanup_redis()

app = FastAPI(lifespan=lifespan)

class OutputHandler:
    def __init__(self):
        self.chunk_size = 64 * 1024  # 64KB chunks
        
    async def handle_connection(self, websocket: WebSocket, task_id: str):
        # 验证task_id格式
        try:
            uuid.UUID(task_id)
        except ValueError:
            await websocket.close(code=4004, reason="Invalid task_id format")
            return
            
        await websocket.accept()
        active_connections[task_id] = websocket
        task_status[task_id] = "connected"
        logger.info(f"Output connection established for task_id: {task_id}")
        
        try:
            # 等待处理结果
            await self._wait_for_result(websocket, task_id)
        except WebSocketDisconnect:
            logger.info(f"Output connection disconnected, task_id: {task_id}")
        except Exception as e:
            logger.error(f"Error in output handler: {e}")
            try:
                await websocket.send_text(json.dumps({
                    "status": "error",
                    "error": str(e)
                }))
            except:
                pass
        finally:
            if task_id in active_connections:
                del active_connections[task_id]
            if task_id in task_status:
                del task_status[task_id]
    
    async def _wait_for_result(self, websocket: WebSocket, task_id: str):
        if not redis_client:
            await websocket.send_text(json.dumps({
                "status": "error",
                "error": "Redis connection not available"
            }))
            return
        
        pubsub = None
        try:
            # 创建新的Redis连接用于订阅
            pubsub = redis_client.pubsub()
            channel_name = f"task_response:{task_id}"
            await pubsub.subscribe(channel_name)
            
            logger.info(f"Subscribed to Redis channel: {channel_name}")
            task_status[task_id] = "waiting"
            
            # 设置超时时间 (5分钟)
            timeout = 300
            start_time = asyncio.get_event_loop().time()
            
            # 跳过订阅确认消息
            async for message in pubsub.listen():
                # 检查超时
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.warning(f"Timeout waiting for response on {channel_name}")
                    await websocket.send_text(json.dumps({
                        "status": "error",
                        "error": "Processing timeout"
                    }))
                    break
                
                # 跳过订阅确认消息
                if message["type"] == "subscribe":
                    logger.debug(f"Subscribed to channel {message['channel']}")
                    continue
                    
                if message["type"] == "message":
                    try:
                        logger.info(f"Received message on {channel_name}: {message['data'][:100]}...")
                        response_data = json.loads(message["data"])
                        await self._send_response(websocket, task_id, response_data)
                        task_status[task_id] = "completed"
                        logger.info(f"Successfully processed response for task {task_id}")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse Redis message: {e}")
                        await websocket.send_text(json.dumps({
                            "status": "error",
                            "error": "Invalid response format"
                        }))
                        break
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        await websocket.send_text(json.dumps({
                            "status": "error",
                            "error": f"Processing error: {str(e)}"
                        }))
                        break
                        
        except Exception as e:
            logger.error(f"Error waiting for Redis response: {e}")
            await websocket.send_text(json.dumps({
                "status": "error",
                "error": "Processing failed"
            }))
        finally:
            # 确保清理订阅
            if pubsub:
                try:
                    await pubsub.unsubscribe(f"task_response:{task_id}")
                    await pubsub.close()
                    logger.debug(f"Cleaned up pubsub for task {task_id}")
                except Exception as e:
                    logger.error(f"Error cleaning up pubsub: {e}")
    
    async def _send_response(self, websocket: WebSocket, task_id: str, response_data: dict):
        try:
            # 发送文本响应
            text_response = {
                "status": "success",
                "task_id": task_id,
                "content": response_data.get("text", ""),
                "audio_present": "audio_file" in response_data and response_data["audio_file"]
            }
            
            await websocket.send_text(json.dumps(text_response))
            logger.info(f"Sent text response for task {task_id}")
            
            # 如果有音频文件，分块发送
            if "audio_file" in response_data and response_data["audio_file"]:
                await self._send_audio_chunks(websocket, task_id, response_data["audio_file"])
                
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            await websocket.send_text(json.dumps({
                "status": "error",
                "error": str(e)
            }))
    
    async def _send_audio_chunks(self, websocket: WebSocket, task_id: str, audio_file: str):
        try:
            audio_path = Path(audio_file)
            if not audio_path.exists():
                logger.warning(f"Audio file not found: {audio_file}")
                return
                
            chunk_id = 0
            file_size = os.path.getsize(audio_path)
            total_chunks = (file_size + self.chunk_size - 1) // self.chunk_size
            
            logger.info(f"Sending audio file {audio_file} in {total_chunks} chunks")
            
            with open(audio_path, "rb") as f:
                while True:
                    chunk_data = f.read(self.chunk_size)
                    if not chunk_data:
                        break
                        
                    # 发送音频块元数据
                    metadata = {
                        "type": "audio_chunk",
                        "task_id": task_id,
                        "chunk_id": chunk_id,
                        "total_chunks": total_chunks
                    }
                    await websocket.send_text(json.dumps(metadata))
                    
                    # 发送音频数据
                    await websocket.send_bytes(chunk_data)
                    chunk_id += 1
                    
                    logger.debug(f"Sent audio chunk {chunk_id}/{total_chunks} for task {task_id}")
                
                # 发送音频完成信号
                await websocket.send_text(json.dumps({
                    "type": "audio_complete",
                    "task_id": task_id
                }))
                
                logger.info(f"Audio transmission completed for task {task_id}")
                
        except Exception as e:
            logger.error(f"Error sending audio chunks: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Audio transmission failed: {str(e)}"
            }))

# 初始化处理器
output_handler = OutputHandler()

@app.websocket("/ws/output/{task_id}")
async def websocket_output_endpoint(websocket: WebSocket, task_id: str):
    await output_handler.handle_connection(websocket, task_id)

@app.get("/")
async def get():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIVtuber Output Handler</title>
    </head>
    <body>
        <h1>AIVtuber Output Handler</h1>
        <p>专用于推送AI处理结果的WebSocket服务</p>
        <ul>
            <li>输出端点: /ws/output/{task_id}</li>
            <li>支持格式: 文本 + 音频(分块传输)</li>
            <li>Redis频道: task_response:{task_id}</li>
        </ul>
        <h2>当前连接状态</h2>
        <p>活跃连接数: """ + str(len(active_connections)) + """</p>
    </body>
    </html>
    """)

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """获取任务状态"""
    status = task_status.get(task_id, "not_found")
    return {
        "task_id": task_id,
        "status": status,
        "connected": task_id in active_connections
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    redis_status = "connected" if redis_client else "disconnected"
    return {
        "status": "ok",
        "redis": redis_status,
        "active_connections": len(active_connections)
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        log_level="info",
        reload=True
    )
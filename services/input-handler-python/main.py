import asyncio
import json
import logging
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
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client: Optional[redis.Redis] = None
active_connections: Dict[str, WebSocket] = {}

# 临时文件存储目录
TEMP_DIR = Path("/tmp/aivtuber_tasks")
TEMP_DIR.mkdir(exist_ok=True)

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
    logger.info("Input Handler shutdown")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    await init_redis()
    logger.info("Input Handler started - ready to receive user inputs")
    yield
    # 关闭时执行
    await cleanup_redis()

app = FastAPI(lifespan=lifespan)

class InputHandler:
    def __init__(self):
        self.chunks: Dict[str, Dict[int, bytes]] = {}
        self.metadata: Dict[str, dict] = {}
        
    async def handle_connection(self, websocket: WebSocket):
        await websocket.accept()
        task_id = str(uuid.uuid4())
        active_connections[task_id] = websocket
        
        # 发送任务ID分配消息
        await websocket.send_text(json.dumps({
            "type": "system",
            "action": "task_id_assigned", 
            "task_id": task_id
        }))
        
        logger.info(f"Input connection established, task_id: {task_id}")
        
        try:
            await self._handle_upload(websocket, task_id)
        except WebSocketDisconnect:
            logger.info(f"Input connection disconnected, task_id: {task_id}")
        except Exception as e:
            logger.error(f"Error in input handler: {e}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": str(e)
            }))
        finally:
            if task_id in active_connections:
                del active_connections[task_id]
            # 清理临时数据
            self._cleanup_task_data(task_id)
    
    async def _handle_upload(self, websocket: WebSocket, task_id: str):
        self.chunks[task_id] = {}
        expected_chunk_id = 0
        
        while True:
            try:
                # 接收消息
                message = await websocket.receive()
                
                if message["type"] == "websocket.disconnect":
                    break
                    
                if "text" in message:
                    # JSON 消息
                    data = json.loads(message["text"])
                    
                    if data.get("action") == "data_chunk":
                        # 元数据消息，记录类型信息
                        self.metadata[task_id] = {
                            "type": data["type"],
                            "chunk_id": data["chunk_id"]
                        }
                        if data["chunk_id"] != expected_chunk_id:
                            await websocket.send_text(
                                f"Chunk ID mismatch: expected {expected_chunk_id}, got {data['chunk_id']}"
                            )
                            continue
                        
                    elif data.get("action") == "upload_complete":
                        # 上传完成，处理数据
                        await self._process_upload(websocket, task_id)
                        break
                        
                elif "bytes" in message:
                    # 二进制数据
                    if task_id not in self.metadata:
                        await websocket.send_text("Error: No metadata received before binary data")
                        continue
                        
                    chunk_id = self.metadata[task_id]["chunk_id"]
                    self.chunks[task_id][chunk_id] = message["bytes"]
                    expected_chunk_id += 1
                    await websocket.send_text("File chunk received")
                    
            except json.JSONDecodeError:
                await websocket.send_text("Invalid JSON format")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_text(f"Error: {str(e)}")
    
    async def _process_upload(self, websocket: WebSocket, task_id: str):
        try:
            # 重组数据
            chunks = self.chunks[task_id]
            data_type = self.metadata[task_id]["type"]
            
            # 按chunk_id排序并合并数据
            combined_data = b"".join([chunks[i] for i in sorted(chunks.keys())])
            
            # 保存到临时文件
            task_dir = TEMP_DIR / task_id
            task_dir.mkdir(exist_ok=True)
            
            if data_type == "text":
                content = combined_data.decode('utf-8')
                input_file = task_dir / "input.txt"
                with open(input_file, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Saved text input for task {task_id}: {content[:100]}...")
                    
            elif data_type == "audio":
                input_file = task_dir / "input.webm"
                with open(input_file, "wb") as f:
                    f.write(combined_data)
                logger.info(f"Saved audio input for task {task_id}, size: {len(combined_data)} bytes")
            
            # 发送处理确认
            await websocket.send_text(json.dumps({
                "type": "system",
                "action": "upload_processed",
                "status": "queued",
                "task_id": task_id
            }))
            
            # 通过Redis发送任务到处理队列
            await self._send_to_redis_queue(task_id, data_type, input_file)
                
        except Exception as e:
            logger.error(f"Error processing upload for task {task_id}: {e}")
            await websocket.send_text(json.dumps({
                "type": "system", 
                "action": "upload_processed",
                "status": "error",
                "error": str(e)
            }))
    
    async def _send_to_redis_queue(self, task_id: str, data_type: str, input_file: Path):
        if redis_client:
            try:
                message = {
                    "task_id": task_id,
                    "type": data_type,
                    "input_file": str(input_file),
                    "timestamp": asyncio.get_event_loop().time()
                }
                
                # 发送到Redis队列，由AI处理模块消费
                await redis_client.lpush("user_input_queue", json.dumps(message))
                logger.info(f"Sent task {task_id} to Redis queue: {data_type}")
                
            except Exception as e:
                logger.error(f"Failed to send task to Redis: {e}")
    
    def _cleanup_task_data(self, task_id: str):
        """清理任务相关的临时数据"""
        if task_id in self.chunks:
            del self.chunks[task_id]
        if task_id in self.metadata:
            del self.metadata[task_id]

# 初始化处理器
input_handler = InputHandler()

@app.websocket("/ws/input")
async def websocket_input_endpoint(websocket: WebSocket):
    await input_handler.handle_connection(websocket)

@app.get("/")
async def get():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIVtuber Input Handler</title>
    </head>
    <body>
        <h1>AIVtuber Input Handler</h1>
        <p>专用于处理用户输入的WebSocket服务</p>
        <ul>
            <li>输入端点: /ws/input</li>
            <li>支持格式: 文本、音频(WebM/Opus)</li>
            <li>Redis队列: user_input_queue</li>
        </ul>
    </body>
    </html>
    """)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )
import asyncio
import json
import logging
import uuid
import httpx
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client: Optional[redis.Redis] = None
active_connections: Dict[str, WebSocket] = {}

# 同步主链路开关与目标地址（M1：仅文本流式）
ENABLE_SYNC_CORE = os.getenv("ENABLE_SYNC_CORE", "false").lower() in {"1", "true", "yes", "on"}
DIALOG_ENGINE_URL = os.getenv("DIALOG_ENGINE_URL", "http://localhost:8100")

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
            
            content = None
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
            
            # 根据 Flag 选择同步链路（SSE）或旧链路（Redis 队列）
            if data_type == "text" and ENABLE_SYNC_CORE:
                asyncio.create_task(self._send_to_dialog_engine(task_id, content or ""))
            else:
                await self._send_to_redis_queue(task_id, data_type, input_file, content)
                
        except Exception as e:
            logger.error(f"Error processing upload for task {task_id}: {e}")
            await websocket.send_text(json.dumps({
                "type": "system", 
                "action": "upload_processed",
                "status": "error",
                "error": str(e)
            }))
    
    async def _send_to_redis_queue(self, task_id: str, data_type: str, input_file: Path, content: str = None):
        if redis_client:
            try:
                logger.info(f"DEBUG: Processing task {task_id}, data_type='{data_type}', content={content is not None}")
                if data_type == "audio":
                    logger.info(f"DEBUG: Routing audio task {task_id} to ASR service")
                    # 音频任务：发送到ASR服务进行语音识别
                    # 根据文件扩展名确定格式
                    file_ext = input_file.suffix.lower()
                    if file_ext == ".webm":
                        audio_format = "webm"
                    elif file_ext == ".mp3":
                        audio_format = "mp3"
                    elif file_ext == ".wav":
                        audio_format = "wav"
                    else:
                        audio_format = "wav"  # 默认
                    
                    asr_message = {
                        "task_id": task_id,
                        "audio": {
                            "type": "file",
                            "path": str(input_file),
                            "format": audio_format,
                            "sample_rate": 16000,
                            "channels": 1
                        },
                        "options": {
                            "lang": "zh",
                            "timestamps": True,
                            "diarization": False
                        },
                        "meta": {
                            "source": "user",
                            "trace_id": None
                        }
                    }
                    await redis_client.lpush("asr_tasks", json.dumps(asr_message, ensure_ascii=False))
                    logger.info(f"Sent audio task {task_id} to ASR queue for recognition")
                    
                else:
                    logger.info(f"DEBUG: Routing text task {task_id} to user input queue")
                    # 文本任务：构造标准化任务消息（B模式：content优先）
                    message = {
                        "task_id": task_id,
                        "type": data_type,
                        "user_id": "anonymous",
                        "input_file": str(input_file),
                        "source": "user",
                        "timestamp": asyncio.get_event_loop().time(),
                        "meta": {
                            "trace_id": None,
                            "from_channel": "input_handler",
                            "provider": "direct_upload"
                        }
                    }
                    
                    # B模式：优先传递content，input_file作为后备
                    if content is not None:
                        message["content"] = content
                    
                    # 文本直接发送到用户输入队列
                    await redis_client.lpush("user_input_queue", json.dumps(message, ensure_ascii=False))
                    logger.info(f"Sent text task {task_id} to user input queue: content_length: {len(content) if content else 0}")
                
            except Exception as e:
                logger.error(f"Failed to send task to Redis: {e}")

    async def _send_to_dialog_engine(self, task_id: str, content: str):
        """调用 dialog-engine 的 /chat/stream（SSE）。失败则回退旧链路。

        说明（M1）：当前仅触发 SSE 流用于验证同步链路；流事件仅记录日志，不转发到前端。
        """
        url = f"{DIALOG_ENGINE_URL.rstrip('/')}/chat/stream"
        payload = {
            "sessionId": task_id,
            "turn": 0,
            "type": "TEXT",
            "content": content,
            "meta": {"lang": "zh"}
        }
        try:
            timeout = httpx.Timeout(connect=2.0, read=30.0, write=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload, headers={"Accept": "text/event-stream"}) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        if line.startswith("event:"):
                            logger.info(f"[SSE] event: {line}")
                        elif line.startswith("data:"):
                            logger.info(f"[SSE] data : {line[:200]}")
            logger.info(f"Dialog-engine SSE completed for task {task_id}")
        except Exception as e:
            logger.warning(f"SSE path failed, fallback to Redis queue. Reason: {e}")
            # 回退：将文本按旧链路入队
            task_dir = TEMP_DIR / task_id
            input_file = task_dir / "input.txt"
            try:
                input_file.parent.mkdir(parents=True, exist_ok=True)
                with open(input_file, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass
            await self._send_to_redis_queue(task_id, "text", input_file, content)
    
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
            <li>订阅: asr_results → 转发为 user_input_queue（content 模式）</li>
        </ul>
    </body>
    </html>
    """)

async def asr_results_bridge():
    """
    订阅 ASR 结果频道 asr_results，将 finished 文本转为 user_input_queue 标准任务（content 优先）。
    """
    if not redis_client:
        logger.error("Redis client not available for ASR bridge")
        return

    pubsub = redis_client.pubsub()
    await pubsub.subscribe("asr_results")
    logger.info("ASR bridge subscribed to channel: asr_results")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except json.JSONDecodeError:
                logger.error("Invalid JSON in asr_results")
                continue

            status = data.get("status")
            text = data.get("text")
            if status != "finished" or not isinstance(text, str) or not text.strip():
                # 跳过非完成或空文本
                continue

            task_id = data.get("task_id") or str(uuid.uuid4())
            lang = data.get("lang")
            meta = data.get("meta") or {}
            user_id = meta.get("user_id", "anonymous")

            unified = {
                "task_id": task_id,
                "type": "text",
                "user_id": user_id,
                "content": text.strip(),
                "source": "asr",
                "timestamp": asyncio.get_event_loop().time(),
                "meta": {
                    "lang": lang,
                    "trace_id": meta.get("trace_id"),
                    "from_channel": "asr_results",
                    "provider": data.get("provider"),
                },
            }

            try:
                await redis_client.lpush("user_input_queue", json.dumps(unified, ensure_ascii=False))
                logger.info(f"Bridged ASR result to user_input_queue, task_id={task_id}, len(text)={len(unified['content'])}")
            except Exception as e:
                logger.error(f"Failed to push unified task to user_input_queue: {e}")

    except Exception as e:
        logger.error(f"ASR bridge error: {e}")
    finally:
        try:
            await pubsub.unsubscribe("asr_results")
            await pubsub.close()
        except Exception:
            pass

@app.on_event("startup")
async def startup_tasks():
    # 启动 ASR → Input 的桥接协程
    asyncio.create_task(asr_results_bridge())

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
        reload=True
    )

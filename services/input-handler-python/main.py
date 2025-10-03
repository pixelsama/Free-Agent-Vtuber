import asyncio
import base64
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import httpx
import redis.asyncio as redis
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
redis_client: Optional[redis.Redis] = None
active_connections: Dict[str, WebSocket] = {}

DIALOG_ENGINE_URL = os.getenv("DIALOG_ENGINE_URL", "http://localhost:8100")
TEXT_STREAM_ENDPOINT = "/chat/stream"
AUDIO_ENDPOINT = "/chat/audio"
VISION_ENDPOINT = "/chat/vision"
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=5.0, read=60.0, write=10.0)

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
                        self.metadata[task_id] = dict(data)
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
            metadata = self.metadata[task_id]
            raw_type = metadata.get("type") if isinstance(metadata, dict) else None
            data_type = raw_type.strip().lower() if isinstance(raw_type, str) else ""

            # 支持内联文本（无需二进制块）
            inline_text = self._extract_inline_text(metadata)

            # 按chunk_id排序并合并数据
            combined_data = b"".join([chunks[i] for i in sorted(chunks.keys())])
            
            # 保存到临时文件
            task_dir = TEMP_DIR / task_id
            task_dir.mkdir(exist_ok=True)
            
            content = None
            if data_type == "text":
                if combined_data:
                    content = combined_data.decode('utf-8')
                elif inline_text is not None:
                    content = inline_text
                else:
                    raise ValueError("text_payload_empty")
                input_file = task_dir / "input.txt"
                with open(input_file, "w", encoding="utf-8") as f:
                    f.write(content)
                logger.info(f"Saved text input for task {task_id}: {content[:100]}...")

            elif data_type == "audio":
                input_file = task_dir / "input.webm"
                with open(input_file, "wb") as f:
                    f.write(combined_data)
                logger.info(f"Saved audio input for task {task_id}, size: {len(combined_data)} bytes")

            elif data_type == "image":
                meta = metadata
                if isinstance(meta, dict):
                    mime_type = meta.get("mime_type") or meta.get("content_type")
                else:
                    mime_type = None
                file_suffix = self._infer_image_suffix(mime_type)
                input_file = task_dir / f"input{file_suffix}"
                with open(input_file, "wb") as f:
                    f.write(combined_data)
                logger.info(
                    "Saved image input for task %s, size: %d bytes, mime: %s",
                    task_id,
                    len(combined_data),
                    mime_type or "unknown",
                )

            # 发送处理确认
            await websocket.send_text(json.dumps({
                "type": "system",
                "action": "upload_processed",
                "status": "queued",
                "task_id": task_id
            }))
            
            if data_type == "text":
                asyncio.create_task(self._handle_text_task(task_id, content or ""))
            elif data_type == "audio":
                asyncio.create_task(self._handle_audio_task(task_id, input_file))
            elif data_type == "image":
                meta = metadata if isinstance(metadata, dict) else {}
                prompt = self._extract_prompt(meta, inline_text)
                extra_meta = meta.get("meta") if isinstance(meta, dict) else None
                mime_type = (
                    meta.get("mime_type") or meta.get("content_type")
                ) if isinstance(meta, dict) else None
                asyncio.create_task(
                    self._handle_image_task(
                        task_id,
                        input_file,
                        prompt,
                        mime_type,
                        extra_meta if isinstance(extra_meta, dict) else None,
                    )
                )
            else:
                logger.warning(f"Unsupported data type '{data_type}' for task {task_id}")
                
        except Exception as e:
            logger.error(f"Error processing upload for task {task_id}: {e}")
            await websocket.send_text(json.dumps({
                "type": "system", 
                "action": "upload_processed",
                "status": "error",
                "error": str(e)
            }))
    
    async def _handle_text_task(self, task_id: str, content: str) -> None:
        try:
            reply, stats = await self._stream_dialog_engine(task_id, content)
            payload = {
                "status": "success",
                "sessionId": task_id,
                "text": reply,
                "transcript": content,
                "stats": stats,
                "source": "dialog-engine",
                "input_mode": "text",
            }
            await self._publish_response(task_id, payload)
        except Exception as exc:
            logger.error(f"Dialog-engine text handling failed for task {task_id}: {exc}")
            await self._publish_error(task_id, str(exc) or "dialog_engine_failed")

    async def _handle_audio_task(self, task_id: str, audio_file: Path) -> None:
        try:
            result = await self._invoke_dialog_engine_audio(task_id, audio_file)
            payload = {
                "status": "success",
                "sessionId": task_id,
                "text": result.get("reply", ""),
                "transcript": result.get("transcript", ""),
                "stats": result.get("stats"),
                "source": "dialog-engine",
                "input_mode": "audio",
            }
            partials = result.get("partials")
            if partials:
                payload["partials"] = partials
            await self._publish_response(task_id, payload)
        except Exception as exc:
            logger.error(f"Dialog-engine audio handling failed for task {task_id}: {exc}")
            await self._publish_error(task_id, str(exc) or "dialog_engine_failed")

    async def _handle_image_task(
        self,
        task_id: str,
        image_file: Path,
        prompt: Optional[str],
        mime_type: Optional[str],
        meta: Optional[Dict[str, Any]],
    ) -> None:
        try:
            result = await self._invoke_dialog_engine_image(
                task_id,
                image_file,
                prompt=prompt,
                mime_type=mime_type,
                meta=meta,
            )
            payload: Dict[str, Any] = {
                "status": "success",
                "sessionId": task_id,
                "text": result.get("reply", ""),
                "transcript": result.get("prompt", ""),
                "stats": result.get("stats"),
                "source": "dialog-engine",
                "input_mode": "image",
            }
            if meta:
                payload["meta"] = meta
            await self._publish_response(task_id, payload)
        except Exception as exc:
            logger.error(f"Dialog-engine image handling failed for task {task_id}: {exc}")
            await self._publish_error(task_id, str(exc) or "dialog_engine_failed")

    async def _publish_response(self, task_id: str, payload: Dict[str, Any]) -> None:
        if not redis_client:
            logger.error("Redis client not available; cannot publish response")
            return
        channel = f"task_response:{task_id}"
        try:
            await redis_client.publish(channel, json.dumps(payload, ensure_ascii=False))
            logger.info(f"Published dialog-engine result to {channel}")
        except Exception as exc:
            logger.error(f"Failed to publish response for task {task_id}: {exc}")

    async def _publish_error(self, task_id: str, message: str) -> None:
        payload = {
            "status": "error",
            "task_id": task_id,
            "error": message,
            "source": "dialog-engine",
        }
        await self._publish_response(task_id, payload)

    async def _stream_dialog_engine(self, task_id: str, content: str) -> Tuple[str, Dict[str, Any]]:
        url = f"{DIALOG_ENGINE_URL.rstrip('/')}{TEXT_STREAM_ENDPOINT}"
        payload = {
            "sessionId": task_id,
            "turn": 0,
            "type": "TEXT",
            "content": content,
            "meta": {"lang": "zh"},
        }
        deltas: list[str] = []
        stats: Dict[str, Any] = {}
        current_event = "message"
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=payload,
                    headers={"Accept": "text/event-stream"},
                ) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line == "":
                            current_event = "message"
                            continue
                        if line.startswith(":"):
                            continue
                        if line.lower().startswith("event:"):
                            current_event = line.split(":", 1)[1].strip() or "message"
                            continue
                        if line.lower().startswith("data:"):
                            data_raw = line.split(":", 1)[1].strip()
                            if not data_raw:
                                continue
                            try:
                                data_obj = json.loads(data_raw)
                            except json.JSONDecodeError:
                                logger.debug(f"Non-JSON SSE data ignored: {data_raw[:50]}")
                                continue
                            if current_event == "text-delta":
                                delta = data_obj.get("content")
                                if isinstance(delta, str):
                                    deltas.append(delta)
                            elif current_event == "done":
                                stats = data_obj.get("stats") or {}
                            elif current_event == "error":
                                raise RuntimeError(data_obj.get("message", "dialog_engine_error"))
            logger.info(f"Dialog-engine SSE completed for task {task_id}")
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            raise RuntimeError(f"dialog_engine_http_error:{exc.response.status_code}:{detail}") from exc
        except Exception:
            raise
        reply_text = "".join(deltas)
        return reply_text, stats

    async def _invoke_dialog_engine_audio(self, task_id: str, audio_file: Path) -> Dict[str, Any]:
        url = f"{DIALOG_ENGINE_URL.rstrip('/')}{AUDIO_ENDPOINT}"
        try:
            audio_bytes = audio_file.read_bytes()
        except Exception as exc:
            raise RuntimeError(f"read_audio_failed:{exc}") from exc
        if not audio_bytes:
            raise RuntimeError("audio_payload_empty")
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        content_type = self._infer_content_type(audio_file.suffix.lower())
        body = {
            "sessionId": task_id,
            "audio": audio_b64,
            "contentType": content_type,
            "meta": {"source": "input-handler"},
        }
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except ValueError:
                detail = exc.response.text
            raise RuntimeError(f"dialog_engine_audio_failed:{detail}") from exc

    async def _invoke_dialog_engine_image(
        self,
        task_id: str,
        image_file: Path,
        *,
        prompt: Optional[str],
        mime_type: Optional[str],
        meta: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        url = f"{DIALOG_ENGINE_URL.rstrip('/')}{VISION_ENDPOINT}"
        try:
            image_bytes = image_file.read_bytes()
        except Exception as exc:
            raise RuntimeError(f"read_image_failed:{exc}") from exc
        if not image_bytes:
            raise RuntimeError("image_payload_empty")
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        body: Dict[str, Any] = {
            "sessionId": task_id,
            "image": image_b64,
        }
        if prompt:
            body["prompt"] = prompt
        if mime_type:
            body["mimeType"] = mime_type
        if meta:
            body["meta"] = meta
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.post(url, json=body)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json()
            except ValueError:
                detail = exc.response.text
            raise RuntimeError(f"dialog_engine_image_failed:{detail}") from exc

    @staticmethod
    def _infer_content_type(suffix: str) -> str:
        mapping = {
            ".webm": "audio/webm",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".m4a": "audio/mp4",
        }
        return mapping.get(suffix, "audio/wav")

    @staticmethod
    def _infer_image_suffix(mime_type: Optional[str]) -> str:
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        if not mime_type:
            return ".png"
        return mapping.get(mime_type.lower(), ".png")

    @staticmethod
    def _extract_inline_text(meta: Any) -> Optional[str]:
        if not isinstance(meta, dict):
            return None
        candidates = [
            meta.get("text"),
            meta.get("content"),
            meta.get("prompt"),
        ]
        for value in candidates:
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
        return None

    @staticmethod
    def _extract_prompt(meta: Any, fallback: Optional[str]) -> Optional[str]:
        if isinstance(meta, dict):
            prompt = meta.get("prompt") or meta.get("text") or meta.get("content")
            if isinstance(prompt, str) and prompt.strip():
                return prompt.strip()
        if isinstance(fallback, str) and fallback.strip():
            return fallback.strip()
        return None

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
            <li>支持格式: 文本、音频(WebM/Opus)、图片(JPEG/PNG/WebP)</li>
            <li>同步链路: 调用 dialog-engine /chat/stream、/chat/audio 与 /chat/vision</li>
            <li>结果分发: 发布 Redis 频道 task_response:&#123;task_id&#125;</li>
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

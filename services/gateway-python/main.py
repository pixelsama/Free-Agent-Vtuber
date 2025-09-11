import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict

import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from src.services.asr_routes import bp_asr as _flask_bp  # type: ignore
from fastapi.middleware.wsgi import WSGIMiddleware
from flask import Flask as _Flask  # shim for mounting Flask blueprint
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 后端服务配置
BACKEND_SERVICES = {
    "input": os.getenv("INPUT_HANDLER_URL", "ws://localhost:8001"),
    "output": os.getenv("OUTPUT_HANDLER_URL", "ws://localhost:8002")
}

# 活跃连接跟踪
active_connections: Dict[str, WebSocket] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    logger.info("API Gateway started on port 8000")
    logger.info(f"Routing to: {BACKEND_SERVICES}")
    yield
    # 关闭时执行
    logger.info("API Gateway shutdown")

app = FastAPI(lifespan=lifespan)
# 将 Flask Blueprint 包装为一个最小 Flask 应用并挂载到 FastAPI
_flask_app = _Flask("gateway_asr_mount")
_flask_app.register_blueprint(_flask_bp)
# 挂载到 /api 前缀（最终路由为 /api/asr）
app.mount("/api", WSGIMiddleware(_flask_app))

# 配置CORS
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class WebSocketProxy:
    def __init__(self):
        self.connection_id = 0
    
    async def proxy_websocket(self, client_ws: WebSocket, backend_url: str, endpoint_type: str):
        """代理WebSocket连接到后端服务"""
        self.connection_id += 1
        conn_id = f"{endpoint_type}_{self.connection_id}"
        
        try:
            # 接受客户端连接
            await client_ws.accept()
            active_connections[conn_id] = client_ws
            logger.info(f"Client connected to {endpoint_type} (ID: {conn_id})")
            
            # 连接到后端服务
            async with websockets.connect(backend_url) as backend_ws:
                logger.info(f"Connected to backend: {backend_url}")
                
                # 创建双向代理任务
                client_to_backend = asyncio.create_task(
                    self._forward_messages(client_ws, backend_ws, f"{conn_id} -> backend")
                )
                backend_to_client = asyncio.create_task(
                    self._forward_messages(backend_ws, client_ws, f"backend -> {conn_id}")
                )
                
                # 等待任一方向的连接断开
                done, pending = await asyncio.wait(
                    [client_to_backend, backend_to_client],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # 取消未完成的任务
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                        
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Backend connection closed for {conn_id}")
        except Exception as e:
            logger.error(f"Error in proxy for {conn_id}: {e}")
            try:
                await client_ws.close(code=1011, reason=f"Proxy error: {str(e)}")
            except:
                pass
        finally:
            if conn_id in active_connections:
                del active_connections[conn_id]
            logger.info(f"Connection {conn_id} cleaned up")
    
    async def _forward_messages(self, source, destination, direction: str):
        """转发消息从source到destination"""
        try:
            if hasattr(source, 'receive'):
                # FastAPI WebSocket
                while True:
                    message = await source.receive()
                    if message["type"] == "websocket.disconnect":
                        logger.info(f"WebSocket disconnect: {direction}")
                        break
                    elif message["type"] == "websocket.receive":
                        if "text" in message:
                            await destination.send(message["text"])
                        elif "bytes" in message:
                            await destination.send(message["bytes"])
            else:
                # websockets library WebSocket
                async for message in source:
                    if isinstance(message, str):
                        await destination.send_text(message)
                    else:
                        await destination.send_bytes(message)
                        
        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {direction}")
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Connection closed: {direction}")
        except Exception as e:
            logger.error(f"Error forwarding message ({direction}): {e}")
            raise

# 初始化代理
proxy = WebSocketProxy()

@app.websocket("/ws/input")
async def proxy_input(websocket: WebSocket):
    """代理输入WebSocket连接到input-handler服务"""
    backend_url = f"{BACKEND_SERVICES['input']}/ws/input"
    await proxy.proxy_websocket(websocket, backend_url, "input")

@app.websocket("/ws/output/{task_id}")
async def proxy_output(websocket: WebSocket, task_id: str):
    """代理输出WebSocket连接到output-handler服务"""
    backend_url = f"{BACKEND_SERVICES['output']}/ws/output/{task_id}"
    await proxy.proxy_websocket(websocket, backend_url, "output")

@app.get("/")
async def get():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AIVtuber API Gateway</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .status { margin: 20px 0; }
            .endpoint { background: #f5f5f5; padding: 10px; margin: 5px 0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>AIVtuber API Gateway</h1>
        <p>统一入口，路由到后端微服务</p>
        
        <div class="status">
            <h2>WebSocket端点</h2>
            <div class="endpoint">
                <strong>输入:</strong> /ws/input → input-handler:8001
            </div>
            <div class="endpoint">
                <strong>输出:</strong> /ws/output/{task_id} → output-handler:8002
            </div>
        </div>
        
        <div class="status">
            <h2>当前状态</h2>
            <p>活跃连接数: """ + str(len(active_connections)) + """</p>
            <p>后端服务: input-handler(8001), output-handler(8002)</p>
        </div>
        
        <div class="status">
            <h2>使用说明</h2>
            <p>前端只需连接8000端口，网关会自动路由到相应的后端服务。</p>
        </div>
    </body>
    </html>
    """)

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "gateway": "running",
        "active_connections": len(active_connections),
        "backend_services": BACKEND_SERVICES
    }

@app.get("/connections")
async def get_connections():
    """获取当前连接状态"""
    return {
        "total_connections": len(active_connections),
        "connections": list(active_connections.keys())
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )

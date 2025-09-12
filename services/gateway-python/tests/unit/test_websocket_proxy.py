import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
import websockets
from websockets.exceptions import ConnectionClosed

# 导入要测试的模块
from main import WebSocketProxy, app


@pytest.mark.asyncio
async def test_websocket_proxy_initialization():
    """测试WebSocketProxy类的初始化"""
    proxy = WebSocketProxy()
    assert proxy.connection_id == 0
    assert isinstance(proxy, WebSocketProxy)


@pytest.mark.asyncio
async def test_proxy_websocket_success(mock_websocket, mock_websocket_connection):
    """测试成功的WebSocket代理连接"""
    proxy = WebSocketProxy()

    # 模拟websockets.connect
    with patch("websockets.connect", return_value=mock_websocket_connection):
        # 模拟_forward_messages方法
        with patch.object(proxy, "_forward_messages", new_callable=AsyncMock):
            await proxy.proxy_websocket(mock_websocket, "ws://localhost:8001", "input")

            # 验证WebSocket连接被接受
            mock_websocket.accept.assert_called_once()

            # 验证连接被添加到活跃连接中
            # 注意：由于是异步测试，实际的连接管理可能在_mock_forward_messages中被处理


@pytest.mark.asyncio
async def test_proxy_websocket_connection_error(mock_websocket):
    """测试WebSocket代理连接错误"""
    proxy = WebSocketProxy()

    # 模拟websockets.connect抛出异常
    with patch("websockets.connect", side_effect=Exception("连接失败")):
        await proxy.proxy_websocket(mock_websocket, "ws://localhost:8001", "input")

        # 验证WebSocket连接被关闭
        mock_websocket.close.assert_called_once_with(
            code=1011, reason="Proxy error: 连接失败"
        )


@pytest.mark.asyncio
async def test_forward_messages_fastapi_websocket(mock_websocket):
    """测试_forward_messages方法处理FastAPI WebSocket"""
    proxy = WebSocketProxy()

    # 创建一个模拟的目标WebSocket
    mock_destination = AsyncMock()

    # 模拟消息流
    messages = [
        {"type": "websocket.receive", "text": "Hello"},
        {"type": "websocket.receive", "bytes": b"binary data"},
        {"type": "websocket.disconnect"},
    ]

    # 设置消息迭代
    mock_websocket.receive.side_effect = messages

    # 调用转发方法
    await proxy._forward_messages(mock_websocket, mock_destination, "test_direction")

    # 验证消息被正确转发
    mock_destination.send.assert_any_call("Hello")
    mock_destination.send.assert_any_call(b"binary data")


@pytest.mark.asyncio
async def test_forward_messages_websockets_library():
    """测试_forward_messages方法处理websockets库WebSocket"""
    proxy = WebSocketProxy()

    class MockWebSocket:
        def __init__(self, msgs):
            self._iter = iter(msgs)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    messages = ["Hello", b"binary data"]
    mock_source = MockWebSocket(messages)
    mock_destination = AsyncMock()

    await proxy._forward_messages(mock_source, mock_destination, "test_direction")

    mock_destination.send_text.assert_called_once_with("Hello")
    mock_destination.send_bytes.assert_called_once_with(b"binary data")


@pytest.mark.asyncio
async def test_forward_messages_websocket_disconnect():
    """测试_forward_messages方法处理WebSocket断开连接"""
    proxy = WebSocketProxy()

    # 创建模拟的源和目标WebSocket
    mock_source = AsyncMock()
    mock_destination = AsyncMock()

    # 模拟WebSocket断开连接异常
    mock_source.receive.side_effect = websockets.exceptions.ConnectionClosed(
        1000, "Normal closure"
    )

    # 调用转发方法，应该不会抛出异常
    await proxy._forward_messages(mock_source, mock_destination, "test_direction")


@pytest.mark.asyncio
async def test_forward_messages_general_exception():
    """测试_forward_messages方法处理一般异常"""
    proxy = WebSocketProxy()

    # 创建模拟的源和目标WebSocket
    mock_source = AsyncMock()
    mock_destination = AsyncMock()

    # 模拟一般异常
    mock_source.receive.side_effect = Exception("General error")

    # 调用转发方法，应该抛出异常
    with pytest.raises(Exception, match="General error"):
        await proxy._forward_messages(mock_source, mock_destination, "test_direction")

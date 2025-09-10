import json
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.message_processor import MessageProcessor

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_mem0_client():
    client = AsyncMock()
    client.add = AsyncMock(return_value="mem_123")
    return client


@pytest.fixture
def mock_redis_client():
    return AsyncMock()


@pytest.fixture
def message_processor(mock_redis_client, mock_mem0_client):
    return MessageProcessor(redis_client=mock_redis_client, mem0_client=mock_mem0_client)


class TestProcessMemoryUpdate:
    async def test_valid_message(self, message_processor, mock_mem0_client):
        message = {"user_id": "u1", "content": "hello"}
        with patch.object(message_processor, "_validate_message_format", wraps=message_processor._validate_message_format) as mock_validate:
            result = await message_processor.process_memory_update(message)
        mock_validate.assert_called_once_with(message)
        mock_mem0_client.add.assert_called_once()
        assert result == {"memory_id": "mem_123", "user_id": "u1", "status": "success"}

    async def test_invalid_message(self, message_processor, mock_mem0_client):
        message = {"user_id": "u1"}
        with patch.object(message_processor, "_validate_message_format", wraps=message_processor._validate_message_format) as mock_validate:
            result = await message_processor.process_memory_update(message)
        mock_validate.assert_called_once_with(message)
        mock_mem0_client.add.assert_not_called()
        assert result == {"error": "invalid_message_format"}


class TestStartMemoryUpdatesSubscription:
    async def test_invalid_json_message(self, mock_mem0_client, caplog):
        redis_client = AsyncMock()
        pubsub = AsyncMock()
        async def listen():
            yield {"type": "message", "data": "not json"}
        pubsub.listen = MagicMock(return_value=listen())
        pubsub.subscribe = AsyncMock()
        redis_client.pubsub = AsyncMock(return_value=pubsub)

        processor = MessageProcessor(redis_client=redis_client, mem0_client=mock_mem0_client)
        processor.process_memory_update = AsyncMock()

        with caplog.at_level(logging.ERROR):
            await processor.start_memory_updates_subscription()

        processor.process_memory_update.assert_not_called()
        assert any("消息JSON解析失败" in record.message for record in caplog.records)

    async def test_processing_exception(self, mock_mem0_client, caplog):
        redis_client = AsyncMock()
        pubsub = AsyncMock()
        valid_data = json.dumps({"user_id": "u1", "content": "hello"})
        async def listen():
            yield {"type": "message", "data": valid_data}
        pubsub.listen = MagicMock(return_value=listen())
        pubsub.subscribe = AsyncMock()
        redis_client.pubsub = AsyncMock(return_value=pubsub)

        processor = MessageProcessor(redis_client=redis_client, mem0_client=mock_mem0_client)
        processor.process_memory_update = AsyncMock(side_effect=Exception("boom"))

        with caplog.at_level(logging.ERROR):
            await processor.start_memory_updates_subscription()

        processor.process_memory_update.assert_called_once()
        assert any("处理订阅消息失败: boom" in record.message for record in caplog.records)

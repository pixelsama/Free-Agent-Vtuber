"""MemoryService tests"""

import pytest
from unittest.mock import AsyncMock

from src.services.memory_service import MemoryService

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_mem0_client():
    return AsyncMock()


@pytest.fixture
def mock_redis_client():
    return AsyncMock()


@pytest.fixture
def memory_service(mock_mem0_client, mock_redis_client):
    return MemoryService(mock_mem0_client, mock_redis_client)


async def test_store_memory_success(memory_service, mock_mem0_client):
    mock_mem0_client.add.return_value = "mem_123"

    memory_id = await memory_service.store_memory("user1", "hello world")

    assert memory_id == "mem_123"
    mock_mem0_client.add.assert_awaited_once()
    # ensure metadata contains service key
    called_metadata = mock_mem0_client.add.call_args.kwargs["metadata"]
    assert called_metadata["service"] == "memory_service"


async def test_store_memory_exception(memory_service, mock_mem0_client):
    mock_mem0_client.add.side_effect = Exception("failed")

    with pytest.raises(Exception):
        await memory_service.store_memory("user1", "hello world")


async def test_search_related_memories_error_returns_empty(memory_service, mock_mem0_client):
    mock_mem0_client.search.side_effect = Exception("error")

    results = await memory_service.search_related_memories("user1", "query")

    assert results == []


async def test_get_user_memories_error_returns_empty(memory_service, mock_mem0_client):
    mock_mem0_client.get_all.side_effect = Exception("boom")

    memories = await memory_service.get_user_memories("user1")

    assert memories == []


async def test_delete_memory_success(memory_service, mock_mem0_client):
    result = await memory_service.delete_memory("mem_1", "user1")

    assert result is True
    mock_mem0_client.delete.assert_awaited_once_with(memory_id="mem_1")


async def test_delete_memory_error_returns_false(memory_service, mock_mem0_client):
    mock_mem0_client.delete.side_effect = Exception("fail")

    result = await memory_service.delete_memory("mem_1", "user1")

    assert result is False

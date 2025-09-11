import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from main import _handle_ltm_requests, _handle_memory_updates


@pytest.mark.asyncio
async def test_handle_memory_updates_processes_and_cleans():
    redis_client = AsyncMock()
    pubsub = AsyncMock()
    redis_client.pubsub = MagicMock(return_value=pubsub)

    message = {
        "type": "message",
        "data": json.dumps(
            {
                "user_id": "user1",
                "content": "hello",
                "source": "conversation",
                "timestamp": 123,
                "meta": {"session_id": "sess1"},
            }
        ),
    }

    async def listen():
        yield message
        await asyncio.sleep(1)

    pubsub.listen = MagicMock(return_value=listen())

    mem0 = AsyncMock()

    task = asyncio.create_task(
        _handle_memory_updates(redis_client, mem0, "memory_updates")
    )
    await asyncio.sleep(0.1)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    mem0.add_memory.assert_called_once_with(
        {
            "user_id": "user1",
            "content": "hello",
            "metadata": {
                "source": "conversation",
                "timestamp": 123,
                "session_id": "sess1",
            },
        }
    )
    pubsub.unsubscribe.assert_called_once_with("memory_updates")
    pubsub.close.assert_called_once()


@pytest.mark.asyncio
async def test_handle_ltm_requests_search_publishes_response():
    redis_client = AsyncMock()
    mem0 = AsyncMock()
    mem0.search.return_value = [{"id": "m1", "memory": "hi"}]

    request = {
        "request_id": "r1",
        "user_id": "u1",
        "type": "search",
        "data": {"query": "hi", "limit": 2},
    }

    redis_client.brpop = AsyncMock(
        side_effect=[("ltm_requests", json.dumps(request)), None]
    )
    redis_client.publish = AsyncMock()

    task = asyncio.create_task(
        _handle_ltm_requests(redis_client, mem0, "ltm_requests", "ltm_responses")
    )
    await asyncio.sleep(0.1)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    mem0.search.assert_called_once_with(query="hi", user_id="u1", limit=2)
    redis_client.publish.assert_called()
    published = json.loads(redis_client.publish.call_args[0][1])
    assert published["request_id"] == "r1"
    assert published["user_id"] == "u1"
    assert published["memories"] == [{"id": "m1", "memory": "hi"}]
    assert published["success"] is True


@pytest.mark.asyncio
async def test_handle_ltm_requests_unknown_type_error():
    redis_client = AsyncMock()
    mem0 = AsyncMock()

    request = {
        "request_id": "r2",
        "user_id": "u2",
        "type": "unknown",
    }

    redis_client.brpop = AsyncMock(
        side_effect=[("ltm_requests", json.dumps(request)), None]
    )
    redis_client.publish = AsyncMock()

    task = asyncio.create_task(
        _handle_ltm_requests(redis_client, mem0, "ltm_requests", "ltm_responses")
    )
    await asyncio.sleep(0.1)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    mem0.search.assert_not_called()
    mem0.add_memory.assert_not_called()
    published = json.loads(redis_client.publish.call_args[0][1])
    assert published["success"] is False
    assert published["error"] == "unknown_request_type:unknown"

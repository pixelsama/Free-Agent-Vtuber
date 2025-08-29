import asyncio
import pytest
from unittest.mock import AsyncMock, patch
import aiohttp
from letta_client import LettaClient, LettaAPIError

@pytest.fixture
def letta_client():
    return LettaClient(base_url="http://localhost:8283", api_key="test-key")

@pytest.mark.asyncio
async def test_health_check_success(letta_client):
    with patch.object(letta_client, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.return_value = {"models": []}
        
        result = await letta_client.health_check()
        
        assert result is True
        mock_request.assert_called_once_with("GET", "/v1/models/")

@pytest.mark.asyncio
async def test_health_check_failure(letta_client):
    with patch.object(letta_client, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = LettaAPIError("Connection failed")
        
        result = await letta_client.health_check()
        
        assert result is False

@pytest.mark.asyncio
async def test_create_agent_success(letta_client):
    with patch.object(letta_client, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_response = {"id": "agent-123", "name": "test-agent"}
        mock_request.return_value = mock_response
        
        result = await letta_client.create_agent("test-agent", "system prompt")
        
        assert result == mock_response
        mock_request.assert_called_once_with(
            "POST", 
            "/v1/agents/", 
            data={"name": "test-agent", "system": "system prompt"}
        )

@pytest.mark.asyncio
async def test_send_message_success(letta_client):
    with patch.object(letta_client, '_make_request', new_callable=AsyncMock) as mock_request:
        mock_response = {
            "messages": [
                {"role": "assistant", "text": "Hello back!"}
            ]
        }
        mock_request.return_value = mock_response
        
        result = await letta_client.send_message("agent-123", "Hello")
        
        assert result == mock_response
        mock_request.assert_called_once_with(
            "POST",
            "/v1/agents/agent-123/messages/",
            data={"message": "Hello", "role": "user", "stream": False}
        )
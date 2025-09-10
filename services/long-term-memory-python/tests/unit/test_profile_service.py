import pytest
from unittest.mock import AsyncMock

from src.services.profile_service import ProfileService

pytestmark = pytest.mark.asyncio


REQUIRED_KEYS = {
    "user_id",
    "preferences",
    "personality_traits",
    "context_info",
    "updated_at",
    "version",
}


def assert_profile_structure(profile: dict):
    """Assert the basic structure of a profile dict."""
    assert REQUIRED_KEYS.issubset(profile.keys())


class TestProfileService:
    async def test_get_user_profile_cache_hit(self):
        user_id = "test_user"
        cached_profile = {
            "user_id": user_id,
            "preferences": ["动漫"],
            "personality_traits": ["内向"],
            "context_info": ["软件工程师"],
            "updated_at": "2024-01-01T00:00:00",
            "version": "1.0",
        }

        mem0_client = AsyncMock()
        redis_client = AsyncMock()
        service = ProfileService(mem0_client, redis_client)
        service._get_cached_profile = AsyncMock(return_value=cached_profile)
        service._cache_profile = AsyncMock()

        result = await service.get_user_profile(user_id)

        service._get_cached_profile.assert_awaited_once_with(user_id)
        service._cache_profile.assert_not_called()
        assert result == cached_profile
        assert_profile_structure(result)

    async def test_get_user_profile_cache_miss_builds_profile(self):
        user_id = "test_user"
        memories = [{"memory": "我喜欢编程和动漫"}]
        built_profile = {
            "user_id": user_id,
            "preferences": ["编程", "动漫"],
            "personality_traits": [],
            "context_info": [],
            "updated_at": "2024-01-01T00:00:00",
            "version": "1.0",
        }

        mem0_client = AsyncMock()
        redis_client = AsyncMock()
        service = ProfileService(mem0_client, redis_client)
        service._get_cached_profile = AsyncMock(return_value=None)
        service._get_user_memories = AsyncMock(return_value=memories)
        service.profile_builder.build_profile = AsyncMock(return_value=built_profile)
        service._cache_profile = AsyncMock()

        result = await service.get_user_profile(user_id)

        service._get_cached_profile.assert_awaited_once_with(user_id)
        service._get_user_memories.assert_awaited_once_with(user_id)
        service.profile_builder.build_profile.assert_awaited_once_with(user_id, memories)
        service._cache_profile.assert_awaited_once_with(user_id, built_profile)
        assert result == built_profile
        assert_profile_structure(result)

    async def test_get_user_profile_returns_empty_on_error(self):
        user_id = "test_user"
        mem0_client = AsyncMock()
        redis_client = AsyncMock()
        service = ProfileService(mem0_client, redis_client)
        service._get_cached_profile = AsyncMock(return_value=None)
        service._get_user_memories = AsyncMock(side_effect=Exception("mem0 error"))
        service._cache_profile = AsyncMock()

        result = await service.get_user_profile(user_id)

        service._get_cached_profile.assert_awaited_once_with(user_id)
        service._get_user_memories.assert_awaited_once_with(user_id)
        service._cache_profile.assert_not_called()
        assert_profile_structure(result)
        assert result["user_id"] == user_id
        assert result["preferences"] == []
        assert result["personality_traits"] == []
        assert result["context_info"] == []


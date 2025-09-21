import pytest

from dialog_engine.ltm_client import LTMInlineClient


@pytest.mark.asyncio
async def test_retrieve_returns_empty_when_not_configured():
    client = LTMInlineClient(base_url=None, retrieve_path="/v1", timeout=1.0, max_snippets=5)

    result = await client.retrieve(session_id="s", user_text="hello", meta={}, limit=None)

    assert result == []


@pytest.mark.asyncio
async def test_retrieve_logs_warning_on_http_error(mocker):
    async def _raise(*args, **kwargs):  # noqa: ANN001
        raise RuntimeError("http fail")

    mocked_client = mocker.patch("httpx.AsyncClient.post", side_effect=_raise)
    client = LTMInlineClient(base_url="http://example.com", retrieve_path="/v1", timeout=1.0, max_snippets=5)

    result = await client.retrieve(session_id="s", user_text="hello", meta={}, limit=None)

    assert result == []
    mocked_client.assert_called_once()

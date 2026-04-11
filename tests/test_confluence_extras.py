import pytest
import httpx

from src.confluence_summarizer.services import confluence
from src.confluence_summarizer.config import settings


def test_get_auth_success():
    old_user = settings.CONFLUENCE_USERNAME
    old_token = settings.CONFLUENCE_API_TOKEN

    settings.CONFLUENCE_USERNAME = "user"
    settings.CONFLUENCE_API_TOKEN = "token"
    try:
        assert confluence._get_auth() == ("user", "token")
    finally:
        settings.CONFLUENCE_USERNAME = old_user
        settings.CONFLUENCE_API_TOKEN = old_token


@pytest.mark.asyncio
async def test_init_client_is_none():
    # Force client to None
    confluence._client = None
    await confluence.init_client()
    assert confluence._client is not None
    await confluence.close_client()


@pytest.mark.asyncio
async def test_init_client_not_none():
    # Calling init_client when _client is already set should do nothing
    confluence._client = httpx.AsyncClient()
    client_ref = confluence._client

    await confluence.init_client()
    assert confluence._client is client_ref
    await confluence.close_client()


@pytest.mark.asyncio
async def test_close_client_when_not_none():
    # Create an actual AsyncClient so aclose() can be called
    confluence._client = httpx.AsyncClient()
    await confluence.close_client()
    assert confluence._client is None


@pytest.mark.asyncio
async def test_get_pages_from_space_with_limit(respx_mock):
    # Mocking a response with multiple results and testing the limit feature
    mock_response = {
        "results": [
            {"id": "1", "title": "A", "body": {"storage": {"value": "x"}}},
            {"id": "2", "title": "B", "body": {"storage": {"value": "y"}}},
            {"id": "3", "title": "C", "body": {"storage": {"value": "z"}}},
        ]
    }

    respx_mock.get(
        f"{settings.CONFLUENCE_URL}/wiki/rest/api/content?spaceKey=TEST&expand=body.storage,version&limit=50"
    ).mock(return_value=httpx.Response(200, json=mock_response))

    # Force _get_client to fallback to an unmanaged client for the test
    confluence._client = None

    pages = await confluence.get_pages_from_space("TEST", limit=2)
    assert len(pages) == 2
    assert pages[0].title == "A"
    assert pages[1].title == "B"


@pytest.mark.asyncio
async def test_update_page(respx_mock):
    confluence._client = None

    respx_mock.put(f"{settings.CONFLUENCE_URL}/wiki/api/v2/pages/123").mock(
        return_value=httpx.Response(200, json={"success": True})
    )

    response = await confluence.update_page("123", "Title", "Body", 2)
    assert response == {"success": True}

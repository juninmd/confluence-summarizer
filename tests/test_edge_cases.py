import logging
from unittest.mock import AsyncMock

import httpx
import pytest

from src.confluence_summarizer.agents import common
from src.confluence_summarizer.config import settings
from src.confluence_summarizer.models.domain import ConfluencePage
from src.confluence_summarizer.services import confluence


@pytest.fixture
def mock_httpx_client():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    # Patch the global client to simulate init
    confluence._client = mock_client
    yield mock_client
    confluence._client = None


@pytest.mark.asyncio
async def test_get_page_success(mock_httpx_client):
    mock_response = httpx.Response(
        status_code=200,
        json={
            "id": "123",
            "title": "Test Page",
            "space": {"key": "TS"},
            "body": {"storage": {"value": "<p>Content</p>"}},
        },
        request=httpx.Request("GET", "http://mock"),
    )
    mock_httpx_client.get.return_value = mock_response

    page = await confluence.get_page("123")
    assert isinstance(page, ConfluencePage)
    assert page.id == "123"
    assert page.title == "Test Page"
    assert page.space_key == "TS"
    assert page.body == "<p>Content</p>"


@pytest.mark.asyncio
async def test_get_page_retry_failure(mock_httpx_client):
    mock_response = httpx.Response(
        status_code=500,
        json={"error": "Server error"},
        request=httpx.Request("GET", "http://mock"),
    )
    mock_httpx_client.get.return_value = mock_response

    from tenacity import RetryError

    with pytest.raises(RetryError):
        await confluence.get_page("123")


@pytest.mark.asyncio
async def test_get_pages_from_space_pagination(mock_httpx_client):
    page_1 = {
        "results": [
            {"id": "1", "title": "Page 1", "body": {"storage": {"value": "Body 1"}}}
        ],
        "_links": {"next": "/next-page"},
    }

    page_2 = {
        "results": [
            {"id": "2", "title": "Page 2", "body": {"storage": {"value": "Body 2"}}}
        ]
    }

    mock_httpx_client.get.side_effect = [
        httpx.Response(200, json=page_1, request=httpx.Request("GET", "http://mock")),
        httpx.Response(200, json=page_2, request=httpx.Request("GET", "http://mock")),
    ]

    pages = await confluence.get_pages_from_space("SPACE", limit=None)
    assert len(pages) == 2
    assert pages[0].id == "1"
    assert pages[1].id == "2"


@pytest.mark.asyncio
async def test_confluence_auth_warning(caplog):
    caplog.set_level(logging.WARNING)
    settings.CONFLUENCE_USERNAME = ""
    settings.CONFLUENCE_API_TOKEN = ""
    auth = confluence._get_auth()
    assert auth is None
    assert "Confluence credentials are not set" in caplog.text


@pytest.mark.asyncio
async def test_agent_common_missing_key(caplog):
    caplog.set_level(logging.WARNING)
    settings.OPENAI_API_KEY = ""
    common._openai_client = None  # force re-init

    client = common._get_client()
    assert client is None
    assert "OPENAI_API_KEY not set" in caplog.text

    res = await common.generate_response("prompt", "system")
    assert "Mock critique" in res


@pytest.mark.asyncio
async def test_confluence_client_unmanaged_warning(caplog):
    caplog.set_level(logging.WARNING)
    confluence._client = None
    client = confluence._get_client()
    assert "Confluence client is not initialized" in caplog.text
    assert isinstance(client, httpx.AsyncClient)

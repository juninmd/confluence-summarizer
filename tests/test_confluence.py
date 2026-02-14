import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from confluence_summarizer.services import confluence


@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as MockClient:
        mock_instance = MockClient.return_value
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.aclose = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_instance.put = AsyncMock()
        yield mock_instance


@pytest.fixture
def reset_confluence_client():
    # Reset singleton before and after test
    confluence._client = None
    yield
    if confluence._client:
        # We can't await in a sync fixture teardown easily if we don't use loop,
        # but for unit test reset logic, just setting to None is enough
        # as we mock the client anyway.
        confluence._client = None


@pytest.mark.asyncio
async def test_init_and_close_client(reset_confluence_client):
    confluence.init_client()
    assert confluence._client is not None

    with patch("httpx.AsyncClient.aclose", new_callable=AsyncMock):
        # We need to manually inject the mock into the real instance created by init_client
        # or mock AsyncClient before init_client.
        # Easier: mock AsyncClient before init_client.
        pass

    await confluence.close_client()
    assert confluence._client is None


@pytest.mark.asyncio
async def test_get_page_success(mock_httpx_client, reset_confluence_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "123",
        "title": "Test Page",
        "body": {"storage": {"value": "Content"}},
        "space": {"key": "SPACE"},
        "version": {"number": 1},
        "_links": {"webui": "/page"}
    }
    mock_httpx_client.get.return_value = mock_response

    # Call with temporary client (since init_client not called)
    page = await confluence.get_page("123")

    assert page.id == "123"
    assert page.title == "Test Page"
    mock_httpx_client.get.assert_called_once()
    mock_httpx_client.aclose.assert_awaited()  # Should close temp client


@pytest.mark.asyncio
async def test_get_page_with_shared_client(mock_httpx_client, reset_confluence_client):
    # Set shared client
    confluence._client = mock_httpx_client

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "123",
        "title": "Test Page",
        "body": {"storage": {"value": "Content"}},
        "space": {"key": "SPACE"},
        "version": {"number": 1},
        "_links": {"webui": "/page"}
    }
    mock_httpx_client.get.return_value = mock_response

    page = await confluence.get_page("123")

    assert page.id == "123"
    # Should NOT close shared client
    mock_httpx_client.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_page(mock_httpx_client, reset_confluence_client):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "123",
        "title": "New Title",
        "body": {"storage": {"value": "New Body"}},
        "space": {"key": "SPACE"},
        "version": {"number": 2},
        "_links": {"webui": "/page"}
    }
    mock_httpx_client.put.return_value = mock_response

    page = await confluence.update_page("123", "New Title", "New Body", 1)

    assert page.version == 2
    mock_httpx_client.put.assert_called_once()

    args, kwargs = mock_httpx_client.put.call_args
    assert kwargs["json"]["title"] == "New Title"
    assert kwargs["json"]["version"]["number"] == 2


@pytest.mark.asyncio
async def test_get_pages_from_space_pagination(mock_httpx_client, reset_confluence_client):
    # Page 1
    mock_resp1 = MagicMock()
    mock_resp1.json.return_value = {
        "results": [{
            "id": "1", "title": "P1", "body": {"storage": {"value": "B1"}},
            "version": {"number": 1}, "_links": {"webui": "/p1"}
        }],
        "_links": {"next": "/next"}
    }

    # Page 2
    mock_resp2 = MagicMock()
    mock_resp2.json.return_value = {
        "results": [{
            "id": "2", "title": "P2", "body": {"storage": {"value": "B2"}},
            "version": {"number": 1}, "_links": {"webui": "/p2"}
        }],
        "_links": {}
    }

    mock_httpx_client.get.side_effect = [mock_resp1, mock_resp2]

    pages = await confluence.get_pages_from_space("SPACE", limit=10)

    assert len(pages) == 2
    assert pages[0].id == "1"
    assert pages[1].id == "2"
    assert mock_httpx_client.get.call_count == 2


@pytest.mark.asyncio
async def test_get_auth_missing_env(mock_httpx_client):
    # Patch the module-level variables
    with patch("confluence_summarizer.services.confluence.CONFLUENCE_USERNAME", ""), \
         patch("confluence_summarizer.services.confluence.CONFLUENCE_API_TOKEN", ""):

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "1", "title": "T", "body": {"storage": {"value": "B"}},
            "space": {"key": "S"}, "version": {"number": 1}, "_links": {"webui": "/"}
        }
        mock_httpx_client.get.return_value = mock_response

        await confluence.get_page("1")

        # Verify auth was None in the call
        args, kwargs = mock_httpx_client.get.call_args
        assert kwargs["auth"] is None


@pytest.mark.asyncio
async def test_get_pages_no_results(mock_httpx_client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_httpx_client.get.return_value = mock_resp

    pages = await confluence.get_pages_from_space("S")
    assert len(pages) == 0


@pytest.mark.asyncio
async def test_get_pages_no_next_link(mock_httpx_client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [{
            "id": "1", "title": "T", "body": {"storage": {"value": "B"}},
            "version": {"number": 1}, "_links": {"webui": "/"}
        }],
        "_links": {"self": "..."}  # _links present but no next
    }
    mock_httpx_client.get.return_value = mock_resp

    pages = await confluence.get_pages_from_space("S")
    assert len(pages) == 1


@pytest.mark.asyncio
async def test_get_pages_limit_reached(mock_httpx_client):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "results": [
            {
                "id": "1", "title": "T1", "body": {"storage": {"value": "B"}},
                "version": {"number": 1}, "_links": {"webui": "/"}
            },
            {
                "id": "2", "title": "T2", "body": {"storage": {"value": "B"}},
                "version": {"number": 1}, "_links": {"webui": "/"}
            }
        ],
        "_links": {"next": "/next"}
    }
    mock_httpx_client.get.return_value = mock_resp

    pages = await confluence.get_pages_from_space("S", limit=1)

    assert len(pages) == 1
    assert pages[0].id == "1"

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from confluence_refiner.services import confluence


@pytest.mark.asyncio
async def test_get_pages_from_space_pagination():
    # Mock responses for pagination
    # Page 1
    mock_response_1 = MagicMock()
    mock_response_1.json.return_value = {
        "results": [{
            "id": "1",
            "title": "Page 1",
            "body": {"storage": {"value": "Body 1"}},
            "version": {"number": 1},
            "_links": {"webui": "/page1"}
        }],
        "_links": {"next": "/next"}
    }
    mock_response_1.raise_for_status = MagicMock()

    # Page 2
    mock_response_2 = MagicMock()
    mock_response_2.json.return_value = {
        "results": [{
            "id": "2",
            "title": "Page 2",
            "body": {"storage": {"value": "Body 2"}},
            "version": {"number": 1},
            "_links": {"webui": "/page2"}
        }],
        "_links": {}  # No next
    }
    mock_response_2.raise_for_status = MagicMock()

    # We need to mock AsyncClient context manager return value
    # and then the get method on that client
    with patch("httpx.AsyncClient") as MockClient:
        mock_client_instance = MockClient.return_value
        mock_client_instance.__aenter__.return_value = mock_client_instance

        # Ensure aclose is an AsyncMock
        mock_client_instance.aclose = AsyncMock()

        # Make get an AsyncMock so it can be awaited
        mock_client_instance.get = AsyncMock(side_effect=[mock_response_1, mock_response_2])

        pages = await confluence.get_pages_from_space("TEST", limit=10)

        assert len(pages) == 2
        assert pages[0].id == "1"
        assert pages[1].id == "2"
        assert mock_client_instance.get.call_count == 2

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.models.domain import ConfluencePage
from src.services import confluence


@pytest.mark.asyncio
async def test_get_page_success():
    mock_data = {
        "id": "12345",
        "title": "Test Page",
        "space": {"key": "TEST"},
        "body": {"storage": {"value": "<p>Content</p>"}},
        "version": {"number": 1},
        "_links": {"webui": "/pages/12345"},
    }

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("src.services.confluence._get_client", return_value=mock_client):
        page = await confluence.get_page("12345")

        assert isinstance(page, ConfluencePage)
        assert page.id == "12345"
        assert page.title == "Test Page"
        assert page.space_key == "TEST"
        assert page.body == "<p>Content</p>"
        assert page.version == 1
        assert "pages/12345" in page.url
        mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_transient_error_mid_pagination_retries_only_that_request():
    """A 503 on page 2 must not refetch page 1 (whole-loop retry did)."""
    from tenacity import wait_none

    req = httpx.Request("GET", "https://dummy.local")
    page_1 = {"results": [{"id": "1", "title": "A"}], "_links": {"next": "/p2"}}
    page_2 = {"results": [{"id": "2", "title": "B"}]}
    mock_client = AsyncMock()
    mock_client.get.side_effect = [
        httpx.Response(200, json=page_1, request=req),
        httpx.Response(503, request=req),
        httpx.Response(200, json=page_2, request=req),
    ]

    with (
        patch("src.services.confluence._get_client", return_value=mock_client),
        patch.object(confluence._get_json.retry, "wait", wait_none()),
    ):
        pages = await confluence.get_pages_from_space("S")

    assert [p.id for p in pages] == ["1", "2"]
    assert mock_client.get.call_count == 3

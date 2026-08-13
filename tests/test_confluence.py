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

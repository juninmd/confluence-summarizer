import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from confluence_summarizer.agents import reviewer
from confluence_summarizer.models import RefinementStatus


@pytest.fixture
def mock_openai():
    # Patch _get_client to return a mock client
    with patch("confluence_summarizer.agents.common._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        yield mock_client


@pytest.mark.asyncio
async def test_reviewer_status_parsing(mock_openai):
    """Test that various positive status strings map to COMPLETED."""
    test_cases = [
        ('{"status": "completed", "comments": "OK"}', RefinementStatus.COMPLETED),
        ('{"status": "Completed", "comments": "OK"}', RefinementStatus.COMPLETED),
        ('{"status": "APPROVED", "comments": "OK"}', RefinementStatus.COMPLETED),
        ('{"status": "approved", "comments": "OK"}', RefinementStatus.COMPLETED),
        ('{"status": "Accepted", "comments": "OK"}', RefinementStatus.COMPLETED),
    ]

    for json_response, expected_status in test_cases:
        with patch("confluence_summarizer.agents.reviewer.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = json_response

            result = await reviewer.review_content("orig", "new", "critique")

            assert result["status"] == expected_status, f"Failed for response: {json_response}"


@pytest.mark.asyncio
async def test_reviewer_rejection_parsing(mock_openai):
    """Test that various negative status strings map to REJECTED."""
    test_cases = [
        ('{"status": "rejected", "comments": "No"}', RefinementStatus.REJECTED),
        ('{"status": "REJECTED", "comments": "No"}', RefinementStatus.REJECTED),
        ('{"status": "changes requested", "comments": "No"}', RefinementStatus.REJECTED),
        ('{"status": "unknown", "comments": "No"}', RefinementStatus.REJECTED),
    ]

    for json_response, expected_status in test_cases:
        with patch("confluence_summarizer.agents.reviewer.call_llm", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = json_response

            result = await reviewer.review_content("orig", "new", "critique")

            assert result["status"] == expected_status, f"Failed for response: {json_response}"

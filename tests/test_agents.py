import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from confluence_refiner.agents import common, analyst, writer, reviewer
from confluence_refiner.models import Critique, RefinementStatus


@pytest.fixture
def mock_openai():
    with patch("confluence_refiner.agents.common.client") as mock:
        yield mock


@pytest.mark.asyncio
async def test_call_llm_success(mock_openai):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test Response"
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    response = await common.call_llm("prompt")
    assert response == "Test Response"
    mock_openai.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_call_llm_json_mode(mock_openai):
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "{}"
    mock_openai.chat.completions.create = AsyncMock(return_value=mock_response)

    await common.call_llm("prompt", json_mode=True)

    call_kwargs = mock_openai.chat.completions.create.call_args[1]
    assert call_kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_call_llm_failure(mock_openai):
    mock_openai.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

    response = await common.call_llm("prompt")
    assert response == ""


@pytest.mark.asyncio
async def test_analyst_success():
    with patch("confluence_refiner.agents.analyst.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """
        {
            "critiques": [
                {
                    "issue_type": "Clarity",
                    "description": "Unclear",
                    "severity": "warning",
                    "suggestion": "Fix"
                }
            ]
        }
        """
        critiques = await analyst.analyze_content("content", ["context"])
        assert len(critiques) == 1
        assert critiques[0].issue_type == "Clarity"


@pytest.mark.asyncio
async def test_analyst_empty_response():
    with patch("confluence_refiner.agents.analyst.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = ""
        critiques = await analyst.analyze_content("content", [])
        assert critiques == []


@pytest.mark.asyncio
async def test_analyst_invalid_json():
    with patch("confluence_refiner.agents.analyst.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "NOT JSON"
        critiques = await analyst.analyze_content("content", [])
        assert critiques == []


@pytest.mark.asyncio
async def test_writer_success():
    with patch("confluence_refiner.agents.writer.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Rewritten Content"
        critique = Critique(issue_type="A", description="B", severity="info", suggestion="C")

        result = await writer.rewrite_content("original", [critique])
        assert result == "Rewritten Content"


@pytest.mark.asyncio
async def test_reviewer_approved():
    with patch("confluence_refiner.agents.reviewer.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"status": "completed", "comments": "LGTM"}'

        result = await reviewer.review_content("org", "new", "critiques")
        assert result["status"] == RefinementStatus.COMPLETED
        assert result["comments"] == "LGTM"


@pytest.mark.asyncio
async def test_reviewer_rejected():
    with patch("confluence_refiner.agents.reviewer.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = '{"status": "rejected", "comments": "Bad"}'

        result = await reviewer.review_content("org", "new", "critiques")
        assert result["status"] == RefinementStatus.REJECTED


@pytest.mark.asyncio
async def test_reviewer_parse_error():
    with patch("confluence_refiner.agents.reviewer.call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "INVALID"

        result = await reviewer.review_content("org", "new", "critiques")
        assert result["status"] == RefinementStatus.FAILED

from unittest.mock import patch

import pytest

from src.confluence_summarizer.agents import analyst, reviewer, writer
from src.confluence_summarizer.agents.common import clean_json_response
from src.confluence_summarizer.models.domain import (
    AnalysisResult,
    Critique,
    CritiqueSeverity,
    RefinementStatus,
)
from src.confluence_summarizer.services import rag


@pytest.mark.asyncio
async def test_analyst_agent_parses_json():
    original_text = "This is an outdated guide."
    mock_response = """```json
    {
      "critiques": [
        {"description": "Outdated word", "severity": "HIGH", "suggestion": "Update it"}
      ]
    }
    ```"""

    with patch(
        "src.confluence_summarizer.agents.analyst.generate_response",
        return_value=mock_response,
    ):
        result = await analyst.analyze_content(original_text, ["Context 1"])

        assert isinstance(result, AnalysisResult)
        assert len(result.critiques) == 1
        # Test lowercase normalization required by Pydantic Model
        assert result.critiques[0].severity == CritiqueSeverity.HIGH
        assert result.critiques[0].description == "Outdated word"


@pytest.mark.asyncio
async def test_analyst_agent_fallback_on_error():
    with patch(
        "src.confluence_summarizer.agents.analyst.generate_response",
        return_value="invalid json",
    ):
        result = await analyst.analyze_content("text", [])
        assert isinstance(result, AnalysisResult)
        assert len(result.critiques) == 0


@pytest.mark.asyncio
async def test_writer_agent_returns_text():
    mock_rewritten = "This is the updated guide."
    critiques = AnalysisResult(
        critiques=[
            Critique(
                description="fix", severity=CritiqueSeverity.LOW, suggestion="do it"
            )
        ]
    )

    with patch(
        "src.confluence_summarizer.agents.writer.generate_response",
        return_value=mock_rewritten,
    ):
        result = await writer.rewrite_content("old text", critiques, ["context"])
        assert result == mock_rewritten


@pytest.mark.asyncio
async def test_reviewer_agent_parses_status():
    mock_response = '{"status": "accepted", "feedback": "Looks good"}'
    critiques = AnalysisResult(critiques=[])

    with patch(
        "src.confluence_summarizer.agents.reviewer.generate_response",
        return_value=mock_response,
    ):
        result = await reviewer.review_content("old text", "new text", critiques)
        assert result.status == RefinementStatus.COMPLETED
        assert result.feedback == "Looks good"


@pytest.mark.asyncio
async def test_reviewer_agent_handles_failed_status():
    mock_response = '{"status": "failed", "feedback": "Bad rewrite"}'
    critiques = AnalysisResult(critiques=[])

    with patch(
        "src.confluence_summarizer.agents.reviewer.generate_response",
        return_value=mock_response,
    ):
        result = await reviewer.review_content("old text", "new text", critiques)
        assert result.status == RefinementStatus.FAILED
        assert result.feedback == "Bad rewrite"


@pytest.mark.asyncio
async def test_reviewer_agent_fallback_on_error():
    critiques = AnalysisResult(critiques=[])

    with patch(
        "src.confluence_summarizer.agents.reviewer.generate_response",
        return_value="not json",
    ):
        result = await reviewer.review_content("old text", "new text", critiques)
        assert result.status == RefinementStatus.FAILED
        assert "Failed to parse" in result.feedback


def test_clean_json_response():
    raw = 'Here is your JSON:\n```json\n{"key": "value"}\n```\nHope it helps.'
    cleaned = clean_json_response(raw)
    assert cleaned == '{"key": "value"}'

    # Test without markdown
    raw_no_md = '{"key": "value"}'
    assert clean_json_response(raw_no_md) == '{"key": "value"}'


def test_chunk_text():
    text = "hello world this is a long text that needs to be chunked"
    # Small chunk size to force splits
    chunks = rag.chunk_text(text, max_chunk_size=20, overlap=5)
    assert len(chunks) > 1
    # Check it made progress
    assert "hello" in chunks[0]

    # Test empty text
    assert rag.chunk_text("") == []

import os
import json
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

import confluence_summarizer.services.confluence as conf_service
from confluence_summarizer.models import RefinementStatus, RefinementJob, AnalysisResult, Critique, ReviewResult
from confluence_summarizer.agents import common, analyst, writer, reviewer
from confluence_summarizer.services.rag import chunk_text

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {"CONFLUENCE_URL": "http://test", "CONFLUENCE_USERNAME": "u", "CONFLUENCE_API_TOKEN": "t", "OPENAI_API_KEY": "sk-123", "CHROMA_DB_PATH": "test_db"}):
        yield

@pytest.fixture
def mock_no_auth():
    with patch.dict(os.environ, {"CONFLUENCE_URL": "http://test", "OPENAI_API_KEY": "sk-123", "CHROMA_DB_PATH": "test_db"}):
        yield

@pytest.mark.asyncio
async def test_confluence_get_page_content(mock_env, httpx_mock):
    conf_service.init_client()
    httpx_mock.add_response(
        url="http://test/wiki/api/v2/pages/123?body-format=storage",
        json={"body": {"storage": {"value": "Test Content"}}}
    )
    content = await conf_service.get_page_content("123")
    assert content == "Test Content"
    await conf_service.close_client()

@pytest.mark.asyncio
async def test_confluence_get_space_pages(mock_env, httpx_mock):
    conf_service.init_client()
    httpx_mock.add_response(
        url="http://test/wiki/api/v2/spaces/TEST/pages?limit=50",
        json={
            "results": [{"id": "1"}, {"id": "2"}],
            "_links": {"next": "/wiki/api/v2/spaces/TEST/pages?cursor=abcd"}
        }
    )
    httpx_mock.add_response(
        url="http://test/wiki/api/v2/spaces/TEST/pages?cursor=abcd",
        json={
            "results": [{"id": "3"}],
            "_links": {}
        }
    )
    pages = await conf_service.get_space_pages("TEST")
    assert len(pages) == 3
    assert pages[0]["id"] == "1"
    assert pages[2]["id"] == "3"
    await conf_service.close_client()

@pytest.mark.asyncio
async def test_analyst_agent(mock_env):
    mock_response = json.dumps({
        "critiques": [{"finding": "Typo", "severity": "LOW", "recommendation": "Fix it"}],
        "overall_quality": "Good"
    })
    with patch("confluence_summarizer.agents.analyst.generate_response", return_value=mock_response):
        result = await analyst.analyze("Some text")
        assert result is not None
        assert result.overall_quality == "Good"
        assert len(result.critiques) == 1
        assert result.critiques[0].severity == "low" # Should be lowercased

@pytest.mark.asyncio
async def test_writer_agent(mock_env):
    critique = Critique(finding="Typo", severity="low", recommendation="Fix")
    analysis = AnalysisResult(critiques=[critique], overall_quality="Good")
    with patch("confluence_summarizer.agents.writer.generate_response", return_value="Rewritten Text"):
        result = await writer.rewrite("Original", analysis, ["Context 1"])
        assert result == "Rewritten Text"

@pytest.mark.asyncio
async def test_reviewer_agent(mock_env):
    mock_response = json.dumps({
        "status": "APPROVED",
        "comments": "Looks good"
    })
    with patch("confluence_summarizer.agents.reviewer.generate_response", return_value=mock_response):
        result = await reviewer.review("Original", "Rewritten")
        assert result is not None
        assert result.status == RefinementStatus.COMPLETED

@pytest.mark.asyncio
async def test_clean_json_response():
    raw = "```json\n{\"test\": 1}\n```"
    cleaned = common.clean_json_response(raw)
    assert cleaned == '{"test": 1}'

    raw2 = "```\n{\"test\": 2}\n```"
    cleaned2 = common.clean_json_response(raw2)
    assert cleaned2 == '{"test": 2}'

def test_chunk_text():
    text = "This is a test sentence that is quite long and we want to split it up based on word boundaries."
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    assert len(chunks) > 0
    assert chunks[0].startswith("This is a test")

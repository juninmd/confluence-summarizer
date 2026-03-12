import os
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

import confluence_summarizer.services.rag as rag
from confluence_summarizer.agents.common import _get_client, clean_json_response, generate_response
from confluence_summarizer.agents.analyst import analyze
from confluence_summarizer.agents.reviewer import review

@pytest.fixture
def mock_env_no_openai():
    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
        yield

@pytest.mark.asyncio
async def test_get_client_missing_key(mock_env_no_openai):
    # Reset singleton
    import confluence_summarizer.agents.common as common
    common._client = None
    client = _get_client()
    assert client is None

@pytest.mark.asyncio
async def test_analyst_no_response():
    with patch("confluence_summarizer.agents.analyst.generate_response", return_value=None):
        res = await analyze("text")
        assert res is None

@pytest.mark.asyncio
async def test_analyst_bad_json():
    with patch("confluence_summarizer.agents.analyst.generate_response", return_value="Not JSON"):
        res = await analyze("text")
        assert res is None

@pytest.mark.asyncio
async def test_reviewer_no_response():
    with patch("confluence_summarizer.agents.reviewer.generate_response", return_value=None):
        res = await review("o", "r")
        assert res is None

@pytest.mark.asyncio
async def test_reviewer_bad_json():
    with patch("confluence_summarizer.agents.reviewer.generate_response", return_value="Not JSON"):
        res = await review("o", "r")
        assert res is None

@pytest.mark.asyncio
async def test_reviewer_invalid_status():
    with patch("confluence_summarizer.agents.reviewer.generate_response", return_value='{"status": "INVALID", "comments": "C"}'):
        res = await review("o", "r")
        assert res is not None
        from confluence_summarizer.models import RefinementStatus
        assert res.status == RefinementStatus.NEEDS_REVISION

@pytest.mark.asyncio
async def test_rag_ingest():
    with patch("confluence_summarizer.services.rag._get_collection") as mock_col:
        mock_instance = MagicMock()
        mock_col.return_value = mock_instance
        await rag.ingest_page("p1", "s1", "Content is long enough to be chunked. " * 50)
        assert mock_instance.delete.call_count == 1
        assert mock_instance.add.call_count == 1

@pytest.mark.asyncio
async def test_rag_ingest_empty():
    with patch("confluence_summarizer.services.rag._get_collection") as mock_col:
        mock_instance = MagicMock()
        mock_col.return_value = mock_instance
        await rag.ingest_page("p1", "s1", "")
        assert mock_instance.delete.call_count == 1
        assert mock_instance.add.call_count == 0

@pytest.mark.asyncio
async def test_rag_query():
    with patch("confluence_summarizer.services.rag._get_collection") as mock_col:
        mock_instance = MagicMock()
        mock_instance.query.return_value = {"documents": [["doc1", "doc2"]]}
        mock_col.return_value = mock_instance
        res = await rag.query_context("test")
        assert res == ["doc1", "doc2"]

@pytest.mark.asyncio
async def test_rag_query_empty():
    with patch("confluence_summarizer.services.rag._get_collection") as mock_col:
        mock_instance = MagicMock()
        mock_instance.query.return_value = {"documents": []}
        mock_col.return_value = mock_instance
        res = await rag.query_context("test")
        assert res == []

    with patch("confluence_summarizer.services.rag._get_collection") as mock_col:
        mock_instance = MagicMock()
        mock_instance.query.return_value = None
        mock_col.return_value = mock_instance
        res = await rag.query_context("test")
        assert res == []

@pytest.mark.asyncio
async def test_generate_response_api_error(mock_env_no_openai):
    import confluence_summarizer.agents.common as common
    common._client = None
    res = await common.generate_response("prompt")
    assert res is None

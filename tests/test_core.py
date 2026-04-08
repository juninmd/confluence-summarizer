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


@pytest.mark.asyncio
async def test_writer_agent_raises_value_error_on_empty():
    critiques = AnalysisResult(critiques=[])
    with patch(
        "src.confluence_summarizer.agents.writer.generate_response", return_value=""
    ):
        with pytest.raises(ValueError, match="empty response"):
            await writer.rewrite_content("old text", critiques, ["context"])


@pytest.mark.asyncio
async def test_reviewer_agent_handles_unknown_status():
    mock_response = '{"status": "unknown", "feedback": "Dunno"}'
    critiques = AnalysisResult(critiques=[])

    with patch(
        "src.confluence_summarizer.agents.reviewer.generate_response",
        return_value=mock_response,
    ):
        result = await reviewer.review_content("old text", "new text", critiques)
        assert result.status == RefinementStatus.PENDING
        assert result.feedback == "Dunno"


@pytest.mark.asyncio
async def test_agents_common_missing_api_key():
    from src.confluence_summarizer.agents import common
    from src.confluence_summarizer.config import settings
    import builtins

    # Force reset
    common._openai_client = None
    old_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = ""

    try:
        # Should return None when OPENAI_API_KEY is not set
        assert common._get_client() is None

        # generate_response should return mock response
        res = await common.generate_response("prompt", "system")
        assert "Mock critique" in res
    finally:
        settings.OPENAI_API_KEY = old_key


@pytest.mark.asyncio
async def test_agents_common_with_api_key():
    from src.confluence_summarizer.agents import common
    from src.confluence_summarizer.config import settings

    # Force reset
    common._openai_client = None
    old_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "test_key"

    class MockChoice:
        class MockMessage:
            content = "Success"
        message = MockMessage()

    class MockResponse:
        choices = [MockChoice()]

    class MockCreate:
        async def create(self, **kwargs):
            return MockResponse()

    class MockChat:
        completions = MockCreate()

    class MockClient:
        chat = MockChat()

    try:
        # get client should initialize it
        client = common._get_client()
        assert client is not None

        # We need to test the generate_response directly bypassing mock patch
        with patch("src.confluence_summarizer.agents.common._get_client", return_value=MockClient()):
            res = await common.generate_response("prompt", "system")
            assert res == "Success"

            # Test empty content
            MockChoice.MockMessage.content = ""
            res = await common.generate_response("prompt", "system")
            assert res == ""
    finally:
        settings.OPENAI_API_KEY = old_key


def test_rag_ingest_page_delete_error():
    from src.confluence_summarizer.models.domain import ConfluencePage

    page = ConfluencePage(id="1", title="test", space_key="T", body="test body", url="x")

    # Mock _get_collection to throw when delete is called
    class MockCollection:
        def delete(self, where):
            raise Exception("Delete failed")

        def add(self, documents, metadatas, ids):
            pass

    with patch("src.confluence_summarizer.services.rag._get_collection", return_value=MockCollection()):
        # Should catch exception and not raise
        rag._ingest_page(page)

def test_rag_get_collection_init():
    import chromadb
    import src.confluence_summarizer.services.rag as rag_module

    rag_module._chroma_client = None
    rag_module._collection = None

    class MockCollection:
        pass

    class MockClient:
        def get_or_create_collection(self, name, metadata):
            return MockCollection()

    with patch.object(chromadb, "PersistentClient", return_value=MockClient()):
        col = rag_module._get_collection()
        assert isinstance(col, MockCollection)

def test_chunk_text():
    text = "hello world this is a long text that needs to be chunked"
    # Small chunk size to force splits
    chunks = rag.chunk_text(text, max_chunk_size=20, overlap=5)
    assert len(chunks) > 1
    # Check it made progress
    assert "hello" in chunks[0]

    # Test empty text
    assert rag.chunk_text("") == []

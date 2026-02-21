import pytest
from unittest.mock import MagicMock, patch
from confluence_summarizer.services import rag
from confluence_summarizer.models import ConfluencePage


@pytest.fixture
def mock_chroma():
    with patch("chromadb.PersistentClient") as mock_client:
        mock_collection = MagicMock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection

        # Reset global state in rag module to force re-initialization
        rag._client = None
        rag._collection = None

        yield mock_collection


def test_chunk_text_simple():
    text = "Hello world this is a test"
    chunks = rag.chunk_text(text, chunk_size=11, overlap=0)
    assert "Hello world" in chunks or "Hello" in chunks


def test_chunk_text_long_word():
    text = "A" * 20
    chunks = rag.chunk_text(text, chunk_size=10, overlap=0)
    assert len(chunks) == 2
    assert chunks[0] == "A" * 10


def test_chunk_text_overlap():
    text = "one two three four"
    chunks = rag.chunk_text(text, chunk_size=8, overlap=2)
    assert len(chunks) > 0


def test_chunk_text_huge_word_force_break():
    # Case where the only break point is at the start, causing no progress
    # " AAAAA" (space at 0). chunk_size=5.
    # segment " AAAA". last_space=0. end -> 0.
    # end <= start (0<=0). Force break -> end=5.
    text = " AAAAA"
    chunks = rag.chunk_text(text, chunk_size=5, overlap=0)
    assert len(chunks) > 0


def test_chunk_text_empty_string():
    text = ""
    chunks = rag.chunk_text(text)
    assert chunks == []


def test_chunk_text_spaces():
    # Covers implicit else of "if chunk:"
    text = "   "
    chunks = rag.chunk_text(text)
    assert chunks == []


def test_chunk_text_invalid_size():
    with pytest.raises(ValueError):
        rag.chunk_text("text", chunk_size=0)
    with pytest.raises(ValueError):
        rag.chunk_text("text", chunk_size=-1)


@pytest.mark.asyncio
async def test_init_rag():
    with patch("confluence_summarizer.services.rag._get_collection") as mock_get_collection:
        await rag.init_rag()
        mock_get_collection.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_page(mock_chroma):
    page = ConfluencePage(
        id="p1", title="Title", body="Content body for test", space_key="S", version=1, url="u"
    )

    await rag.ingest_page(page)

    # Verify delete called
    mock_chroma.delete.assert_called_once()

    # Verify upsert called
    mock_chroma.upsert.assert_called_once()
    call_args = mock_chroma.upsert.call_args[1]
    assert len(call_args["ids"]) == 1
    assert call_args["documents"][0] == "Content body for test"
    assert call_args["metadatas"][0]["page_id"] == "p1"


@pytest.mark.asyncio
async def test_ingest_page_empty(mock_chroma):
    page = ConfluencePage(
        id="p2", title="Title", body="", space_key="S", version=1, url="u"
    )
    await rag.ingest_page(page)
    # Upsert should not be called if chunks are empty
    mock_chroma.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_page_delete_error(mock_chroma):
    mock_chroma.delete.side_effect = Exception("Delete failed")
    page = ConfluencePage(
        id="p1", title="Title", body="Content", space_key="S", version=1, url="u"
    )
    # Should not raise
    await rag.ingest_page(page)
    mock_chroma.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_query_context(mock_chroma):
    mock_chroma.query.return_value = {
        "documents": [["doc1", "doc2"]]
    }

    results = await rag.query_context("query")

    assert results == ["doc1", "doc2"]
    mock_chroma.query.assert_called_once()


@pytest.mark.asyncio
async def test_query_context_exclude(mock_chroma):
    mock_chroma.query.return_value = {"documents": [[]]}

    await rag.query_context("query", exclude_page_id="p1")

    args = mock_chroma.query.call_args[1]
    assert args["where"] == {"page_id": {"$ne": "p1"}}


@pytest.mark.asyncio
async def test_query_context_empty(mock_chroma):
    mock_chroma.query.return_value = {"documents": []}
    results = await rag.query_context("query")
    assert results == []

    mock_chroma.query.return_value = {}  # No documents key
    results = await rag.query_context("query")
    assert results == []


@pytest.mark.asyncio
async def test_query_context_none_results(mock_chroma):
    mock_chroma.query.return_value = None
    results = await rag.query_context("query")
    assert results == []


@pytest.mark.asyncio
async def test_query_context_documents_is_none(mock_chroma):
    mock_chroma.query.return_value = {"documents": None}
    results = await rag.query_context("query")
    assert results == []

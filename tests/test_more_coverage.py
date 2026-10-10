import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.models.domain import (
    ConfluencePage,
    RefinementJob,
    RefinementStatus,
)
from src.services import confluence, rag
from tests.fakes import FakePool
from src.tasks import (
    _perform_refinement,
    process_space_refinement,
)


@pytest.fixture
def mock_chroma():
    """Fake pgvector pool + embeddings (name kept for the unrelated tests using it)."""
    from src.db import pool

    fake = FakePool()
    pool._pool = fake  # type: ignore[assignment]
    with patch(
        "src.services.rag.embed_texts",
        new=AsyncMock(side_effect=lambda texts: [[0.1, 0.2] for _ in texts]),
    ):
        yield fake.conn
    pool._pool = None


@pytest.mark.asyncio
async def test_rag_ingest_page(mock_chroma):
    page = ConfluencePage(id="1", title="T", space_key="S", body="body")
    await rag.ingest_page(page)

    assert "DELETE FROM chunks WHERE page_id = $1" in mock_chroma.sql("execute")
    rows = mock_chroma.calls[-1][2][0]
    assert rows == [("1", 0, "S", "body", "[0.1,0.2]")]

    # Explicit text (the backup indexes Markdown, not the HTML body)
    mock_chroma.calls.clear()
    await rag.ingest_page(page, text="markdown text")
    assert mock_chroma.calls[-1][2][0][0][3] == "markdown text"

    # Empty body: old chunks are removed, nothing is inserted
    page_empty = ConfluencePage(id="2", title="T", space_key="S", body="")
    mock_chroma.calls.clear()
    await rag.ingest_page(page_empty)
    assert mock_chroma.sql("executemany") == []
    assert len(mock_chroma.sql("execute")) == 1


@pytest.mark.asyncio
async def test_rag_query_context(mock_chroma):
    mock_chroma.rows = [{"content": "doc1"}]
    results = await rag.query_context("query")
    assert results == ["doc1"]
    assert "<=>" in mock_chroma.sql("fetch")[0]


@pytest.mark.asyncio
async def test_rag_query_context_empty(mock_chroma):
    results = await rag.query_context("query")
    assert results == []


@pytest.mark.asyncio
async def test_perform_refinement_error_handling(caplog):
    caplog.set_level(logging.ERROR)
    job = RefinementJob(id="job1", page_id="1", status=RefinementStatus.PENDING)
    page = ConfluencePage(id="1", title="T", space_key="S", body="body")

    with patch("src.services.rag.query_context", new_callable=AsyncMock) as m_query:
        m_query.side_effect = Exception("Mock RAG Error")
        await _perform_refinement(job, page)

    assert job.status == RefinementStatus.FAILED
    assert "Mock RAG Error" in job.error
    assert "Error processing job job1" in caplog.text


@pytest.mark.asyncio
async def test_process_space_refinement_exception(caplog):
    caplog.set_level(logging.ERROR)

    with patch(
        "src.services.confluence.get_pages_from_space",
        new_callable=AsyncMock,
    ) as m_get:
        m_get.side_effect = Exception("Space API Error")
        await process_space_refinement("TEST")

    assert "Error processing space TEST" in caplog.text


@pytest.mark.asyncio
async def test_get_pages_pagination_no_links(mock_chroma):
    with patch("src.services.confluence._get_client") as m_client_getter:
        m_client = AsyncMock()
        m_client_getter.return_value = m_client
        m_response = httpx.Response(
            200,
            json={"results": []},
            request=httpx.Request("GET", "https://dummy.local"),
        )
        m_client.get.return_value = m_response

        pages = await confluence.get_pages_from_space("S")
        assert len(pages) == 0


@pytest.mark.asyncio
async def test_update_page_failure(mock_chroma):
    with patch("src.services.confluence._get_client") as m_client_getter:
        m_client = AsyncMock()
        m_client_getter.return_value = m_client
        m_response = httpx.Response(
            500,
            json={"error": "fail"},
            request=httpx.Request("PUT", "https://dummy.local"),
        )
        m_client.put.return_value = m_response

        from tenacity import RetryError

        with pytest.raises(RetryError):
            await confluence.update_page("1", "T", "B", 2)


@pytest.mark.asyncio
async def test_rag_query_context_redis_cache():
    with patch("src.services.rag._get_redis") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Test Cache Hit
        mock_redis.get.return_value = '["doc1_cached"]'
        results = await rag.query_context("query_hit")
        assert results == ["doc1_cached"]
        assert mock_redis.get.called

        # Test Cache Miss and Write
        mock_redis.reset_mock()
        mock_redis.get.return_value = None
        with patch("src.services.rag._query_context", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = ["doc1_db"]
            results = await rag.query_context("query_miss")
            assert results == ["doc1_db"]
            assert mock_redis.get.called
            assert mock_redis.setex.called


@pytest.mark.asyncio
async def test_get_redis_client():
    from src.config import settings

    original_url = settings.REDIS_URL

    try:
        # Ensure it handles REDIS_URL properly
        with patch("redis.asyncio.from_url") as mock_from_url:
            settings.REDIS_URL = "redis://localhost:6379"

            # Clear global to test initialization
            import src.services.rag as rag_module

            rag_module._redis_client = None

            client = rag_module._get_redis()
            assert client is not None
            assert mock_from_url.called

    finally:
        # Cleanup
        import src.services.rag as rag_module

        settings.REDIS_URL = original_url
        rag_module._redis_client = None


@pytest.mark.asyncio
async def test_rag_query_context_redis_cache_exceptions():
    with patch("src.services.rag._get_redis") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Test Cache Read Exception
        mock_redis.get.side_effect = Exception("Redis Read Error")
        with patch("src.services.rag._query_context", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = ["doc1_db"]
            results = await rag.query_context("query_read_err")
            assert results == ["doc1_db"]
            assert mock_redis.get.called

        # Test Cache Write Exception
        mock_redis.reset_mock()
        mock_redis.get.side_effect = None
        mock_redis.get.return_value = None
        mock_redis.setex.side_effect = Exception("Redis Write Error")
        with patch("src.services.rag._query_context", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = ["doc1_db"]
            results = await rag.query_context("query_write_err")
            assert results == ["doc1_db"]
            assert mock_redis.setex.called

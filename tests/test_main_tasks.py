import pytest
from unittest.mock import AsyncMock, patch
from confluence_summarizer.main import (
    process_refinement,
    process_space_ingestion,
    process_space_refinement,
    process_page_ingestion,
)
from confluence_summarizer.models import RefinementStatus, ConfluencePage


@pytest.fixture
def mock_confluence():
    with patch("confluence_summarizer.main.confluence", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_rag():
    with patch("confluence_summarizer.main.rag", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_db():
    with patch("confluence_summarizer.main.database", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_refine_page():
    with patch("confluence_summarizer.main.refine_page", new_callable=AsyncMock) as mock:
        yield mock


@pytest.mark.asyncio
async def test_process_refinement_success(mock_confluence, mock_refine_page, mock_db):
    mock_confluence.get_page.return_value = ConfluencePage(
        id="1", title="T", body="B", space_key="S", version=1, url="u"
    )
    result_mock = AsyncMock()
    mock_refine_page.return_value = result_mock

    await process_refinement("1")

    mock_confluence.get_page.assert_called_with("1")
    mock_refine_page.assert_called_once()
    mock_db.save_job.assert_called_with(result_mock)


@pytest.mark.asyncio
async def test_process_refinement_failure(mock_confluence, mock_db):
    mock_confluence.get_page.side_effect = Exception("Fail")

    await process_refinement("1")

    mock_db.save_job.assert_called_once()
    saved_job = mock_db.save_job.call_args[0][0]
    assert saved_job.status == RefinementStatus.FAILED
    assert "Fail" in saved_job.reviewer_comments


@pytest.mark.asyncio
async def test_process_space_ingestion_success(mock_confluence, mock_rag):
    mock_confluence.get_pages_from_space.return_value = [
        ConfluencePage(id="1", title="T1", body="B1", space_key="S", version=1, url="u1"),
        ConfluencePage(id="2", title="T2", body="B2", space_key="S", version=1, url="u2"),
    ]

    await process_space_ingestion("S")

    assert mock_rag.ingest_page.call_count == 2


@pytest.mark.asyncio
async def test_process_space_ingestion_failure(mock_confluence):
    # This just prints to stdout, so we just check it doesn't raise
    mock_confluence.get_pages_from_space.side_effect = Exception("Fail")

    await process_space_ingestion("S")
    # Should complete without error


@pytest.mark.asyncio
async def test_process_page_ingestion_success(mock_confluence, mock_rag):
    mock_confluence.get_page.return_value = ConfluencePage(
        id="1", title="T", body="B", space_key="S", version=1, url="u"
    )

    await process_page_ingestion("1")

    mock_rag.ingest_page.assert_called_once()


@pytest.mark.asyncio
async def test_process_page_ingestion_failure(mock_confluence):
    mock_confluence.get_page.side_effect = Exception("Fail")

    # Should not raise
    await process_page_ingestion("1")


@pytest.mark.asyncio
async def test_process_space_refinement_success(mock_confluence, mock_refine_page, mock_db):
    mock_confluence.get_pages_from_space.return_value = [
        ConfluencePage(id="1", title="T1", body="B1", space_key="S", version=1, url="u1"),
        ConfluencePage(id="2", title="T2", body="B2", space_key="S", version=1, url="u2"),
    ]

    result_mock = AsyncMock()
    result_mock.status = RefinementStatus.COMPLETED
    mock_refine_page.return_value = result_mock

    await process_space_refinement("S")

    assert mock_confluence.get_pages_from_space.call_count == 1
    assert mock_refine_page.call_count == 2
    assert mock_db.save_job.call_count == 2


@pytest.mark.asyncio
async def test_process_space_refinement_partial_failure(mock_confluence, mock_refine_page, mock_db):
    """Test that one page failing refinement doesn't stop others."""
    p1 = ConfluencePage(id="1", title="T1", body="B1", space_key="S", version=1, url="u1")
    p2 = ConfluencePage(id="2", title="T2", body="B2", space_key="S", version=1, url="u2")
    mock_confluence.get_pages_from_space.return_value = [p1, p2]

    # First call succeeds, second fails
    mock_refine_page.side_effect = [AsyncMock(), Exception("Refinement Failed")]

    await process_space_refinement("S")

    assert mock_refine_page.call_count == 2
    # Both should trigger a save (one success, one failure report)
    assert mock_db.save_job.call_count == 2

    # Check the second save call was a failure
    calls = mock_db.save_job.call_args_list
    # Note: order is not guaranteed with asyncio.gather, but usually consistent for small list
    # We just check that ONE of them was failed
    statuses = [call[0][0].status for call in calls]
    # Since mock_refine_page.return_value was AsyncMock, its status attribute might be mock default.
    # But for the Exception case, we explicitly create a result with FAILED.
    assert RefinementStatus.FAILED in statuses


@pytest.mark.asyncio
async def test_process_space_refinement_failure(mock_confluence):
    # Test top-level failure (e.g. fetching pages failed)
    mock_confluence.get_pages_from_space.side_effect = Exception("Total Fail")

    # Should log error and complete without raising
    await process_space_refinement("S")

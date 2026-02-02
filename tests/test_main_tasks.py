import pytest
from unittest.mock import AsyncMock, patch
from confluence_refiner.main import process_refinement, process_space_ingestion
from confluence_refiner.models import RefinementStatus, ConfluencePage


@pytest.fixture
def mock_confluence():
    with patch("confluence_refiner.main.confluence", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_rag():
    with patch("confluence_refiner.main.rag", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_db():
    with patch("confluence_refiner.main.db", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_refine_page():
    with patch("confluence_refiner.main.refine_page", new_callable=AsyncMock) as mock:
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
        ConfluencePage(id="1", title="T", body="B", space_key="S", version=1, url="u")
    ]

    await process_space_ingestion("S")

    mock_rag.ingest_page.assert_called_once()


@pytest.mark.asyncio
async def test_process_space_ingestion_failure(mock_confluence):
    # This just prints to stdout, so we just check it doesn't raise
    mock_confluence.get_pages_from_space.side_effect = Exception("Fail")

    await process_space_ingestion("S")
    # Should complete without error

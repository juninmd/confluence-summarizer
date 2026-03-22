from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.confluence_summarizer import config
from src.confluence_summarizer.agents.reviewer import ReviewResult
from src.confluence_summarizer.database import init_db, save_job_sync
from src.confluence_summarizer.main import (
    _perform_refinement,
    app,
    process_refinement_job,
    process_space_refinement,
)
from src.confluence_summarizer.models.domain import (
    AnalysisResult,
    ConfluencePage,
    Critique,
    CritiqueSeverity,
    RefinementJob,
    RefinementStatus,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    db_path = tmp_path / "test_jobs.db"
    config.settings.DB_PATH = str(db_path)
    init_db()


@pytest.fixture
def mock_confluence_client():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    with patch(
        "src.confluence_summarizer.services.confluence._get_client",
        return_value=mock_client,
    ):
        yield mock_client


@pytest.mark.asyncio
async def test_perform_refinement_no_critiques():
    job = RefinementJob(id="job1", page_id="page1", status=RefinementStatus.PENDING)
    page = ConfluencePage(id="page1", title="Title", space_key="KEY", body="Text")

    with patch(
        "src.confluence_summarizer.services.rag.query_context", new_callable=AsyncMock
    ) as mock_query:
        mock_query.return_value = []
        with patch(
            "src.confluence_summarizer.agents.analyst.analyze_content",
            new_callable=AsyncMock,
        ) as mock_analyze:
            mock_analyze.return_value = AnalysisResult(critiques=[])
            await _perform_refinement(job, page)

            assert job.status == RefinementStatus.COMPLETED
            assert job.refined_text == "Text"


@pytest.mark.asyncio
async def test_perform_refinement_with_critiques():
    job = RefinementJob(id="job1", page_id="page1", status=RefinementStatus.PENDING)
    page = ConfluencePage(id="page1", title="Title", space_key="KEY", body="Text")

    analysis = AnalysisResult(
        critiques=[
            Critique(
                description="Bad", severity=CritiqueSeverity.HIGH, suggestion="Fix"
            )
        ]
    )
    review = ReviewResult(status=RefinementStatus.COMPLETED, feedback="Good")

    with (
        patch(
            "src.confluence_summarizer.services.rag.query_context",
            new_callable=AsyncMock,
        ) as m_query,
        patch(
            "src.confluence_summarizer.agents.analyst.analyze_content",
            new_callable=AsyncMock,
        ) as m_analyze,
        patch(
            "src.confluence_summarizer.agents.writer.rewrite_content",
            new_callable=AsyncMock,
        ) as m_rewrite,
        patch(
            "src.confluence_summarizer.agents.reviewer.review_content",
            new_callable=AsyncMock,
        ) as m_review,
    ):
        m_query.return_value = []
        m_analyze.return_value = analysis
        m_rewrite.return_value = "New Text"
        m_review.return_value = review

        await _perform_refinement(job, page)

        assert job.status == RefinementStatus.COMPLETED
        assert job.refined_text == "New Text"


@pytest.mark.asyncio
async def test_perform_refinement_rejected_review():
    job = RefinementJob(id="job1", page_id="page1", status=RefinementStatus.PENDING)
    page = ConfluencePage(id="page1", title="Title", space_key="KEY", body="Text")

    analysis = AnalysisResult(
        critiques=[
            Critique(
                description="Bad", severity=CritiqueSeverity.HIGH, suggestion="Fix"
            )
        ]
    )
    review = ReviewResult(status=RefinementStatus.FAILED, feedback="Bad rewrite")

    with (
        patch(
            "src.confluence_summarizer.services.rag.query_context",
            new_callable=AsyncMock,
        ) as m_query,
        patch(
            "src.confluence_summarizer.agents.analyst.analyze_content",
            new_callable=AsyncMock,
        ) as m_analyze,
        patch(
            "src.confluence_summarizer.agents.writer.rewrite_content",
            new_callable=AsyncMock,
        ) as m_rewrite,
        patch(
            "src.confluence_summarizer.agents.reviewer.review_content",
            new_callable=AsyncMock,
        ) as m_review,
    ):
        m_query.return_value = []
        m_analyze.return_value = analysis
        m_rewrite.return_value = "New Text"
        m_review.return_value = review

        await _perform_refinement(job, page)

        assert job.status == RefinementStatus.FAILED
        assert "Bad rewrite" in job.error


@pytest.mark.asyncio
async def test_perform_refinement_exception():
    job = RefinementJob(id="job1", page_id="page1", status=RefinementStatus.PENDING)
    page = ConfluencePage(id="page1", title="Title", space_key="KEY", body="Text")

    with patch(
        "src.confluence_summarizer.services.rag.query_context", new_callable=AsyncMock
    ) as m_query:
        m_query.side_effect = Exception("RAG Failure")
        await _perform_refinement(job, page)

        assert job.status == RefinementStatus.FAILED
        assert "RAG Failure" in job.error


@pytest.mark.asyncio
async def test_process_refinement_job_success():
    job = RefinementJob(id="job1", page_id="page1", status=RefinementStatus.PENDING)
    save_job_sync(job)

    page = ConfluencePage(id="page1", title="Title", space_key="KEY", body="Text")
    with patch(
        "src.confluence_summarizer.services.confluence.get_page", new_callable=AsyncMock
    ) as mock_get_page:
        mock_get_page.return_value = page
        with patch(
            "src.confluence_summarizer.main._perform_refinement", new_callable=AsyncMock
        ) as mock_perform:
            await process_refinement_job(job)
            assert mock_perform.called


@pytest.mark.asyncio
async def test_process_refinement_job_failure():
    job = RefinementJob(id="job1", page_id="page1", status=RefinementStatus.PENDING)
    save_job_sync(job)

    with patch(
        "src.confluence_summarizer.services.confluence.get_page", new_callable=AsyncMock
    ) as mock_get_page:
        mock_get_page.side_effect = Exception("API Error")
        await process_refinement_job(job)
        assert job.status == RefinementStatus.FAILED
        assert "API Error" in job.error


@pytest.mark.asyncio
async def test_process_space_refinement():
    page = ConfluencePage(id="page1", title="Title", space_key="SPACE", body="Text")

    with (
        patch(
            "src.confluence_summarizer.services.confluence.get_pages_from_space",
            new_callable=AsyncMock,
        ) as mock_get_pages,
        patch(
            "src.confluence_summarizer.services.rag.ingest_page", new_callable=AsyncMock
        ) as mock_ingest,
        patch("asyncio.create_task") as mock_create_task,
    ):
        mock_get_pages.return_value = [page]
        await process_space_refinement("SPACE")

        assert mock_get_pages.called
        assert mock_ingest.called
        assert mock_create_task.called


@pytest.mark.asyncio
async def test_publish_page_success(mock_confluence_client):
    job = RefinementJob(
        id="pub-job",
        page_id="page1",
        status=RefinementStatus.COMPLETED,
        refined_text="New text",
    )
    save_job_sync(job)

    page = ConfluencePage(id="page1", title="Title", space_key="SPACE", body="Old text")
    with (
        patch(
            "src.confluence_summarizer.services.confluence.get_page",
            new_callable=AsyncMock,
        ) as mock_get_page,
        patch(
            "src.confluence_summarizer.services.confluence.update_page",
            new_callable=AsyncMock,
        ) as mock_update_page,
    ):
        mock_get_page.return_value = page

        response = client.post("/publish/pub-job")
        assert response.status_code == 200
        assert response.json()["message"] == "Page published successfully"
        assert mock_update_page.called


@pytest.mark.asyncio
async def test_publish_page_not_found():
    response = client.post("/publish/missing-job")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_publish_page_invalid_status():
    job = RefinementJob(id="bad-job", page_id="page1", status=RefinementStatus.PENDING)
    save_job_sync(job)

    response = client.post("/publish/bad-job")
    assert response.status_code == 400
    assert "Job must be completed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_publish_page_failure():
    job = RefinementJob(
        id="fail-job",
        page_id="page1",
        status=RefinementStatus.COMPLETED,
        refined_text="New text",
    )
    save_job_sync(job)

    with patch(
        "src.confluence_summarizer.services.confluence.get_page", new_callable=AsyncMock
    ) as mock_get_page:
        mock_get_page.side_effect = Exception("Confluence Down")

        response = client.post("/publish/fail-job")
        assert response.status_code == 500
        assert "Publishing failed" in response.json()["detail"]

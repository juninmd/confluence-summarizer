from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from src.confluence_summarizer import config
from src.confluence_summarizer.database import init_db, save_job_sync
from src.confluence_summarizer.main import app
from src.confluence_summarizer.models.domain import (
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
async def test_refine_page_endpoint(mock_confluence_client):
    # Mocking background tasks to not actually run for the endpoint test
    with patch(
        "src.confluence_summarizer.main.BackgroundTasks.add_task"
    ) as mock_add_task:
        response = client.post(
            "/refine/test-page-id", headers={"X-API-Key": "dummy-api-key"}
        )

        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Refinement job accepted"
        assert "job_id" in data
        assert data["page_id"] == "test-page-id"

        # Check background task was queued
        assert mock_add_task.called


@pytest.mark.asyncio
async def test_refine_space_endpoint():
    with patch(
        "src.confluence_summarizer.main.BackgroundTasks.add_task"
    ) as mock_add_task:
        response = client.post(
            "/refine/space/TESTSPACE", headers={"X-API-Key": "dummy-api-key"}
        )

        assert response.status_code == 202
        data = response.json()
        assert data["message"] == "Space refinement job accepted"
        assert data["space_key"] == "TESTSPACE"
        assert mock_add_task.called


@pytest.mark.asyncio
async def test_get_status_endpoint():
    job = RefinementJob(
        id="test-job-id",
        page_id="test-page-id",
        status=RefinementStatus.COMPLETED,
        refined_text="Done.",
    )
    save_job_sync(job)

    response = client.get("/status/test-job-id", headers={"X-API-Key": "dummy-api-key"})
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test-job-id"
    assert data["status"] == "completed"
    assert data["refined_text"] == "Done."


@pytest.mark.asyncio
async def test_get_status_not_found():
    response = client.get(
        "/status/non-existent-job", headers={"X-API-Key": "dummy-api-key"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Job not found"}

import os
import json
import pytest
import sqlite3
import chromadb
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient

from confluence_summarizer.models import RefinementJob, RefinementStatus, AnalysisResult, Critique, ReviewResult
from confluence_summarizer.database import init_db, save_job, get_job, get_jobs_by_space, DB_PATH
from confluence_summarizer.main import _perform_refinement, _process_space, app
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def setup_db():
    # Use an in-memory db or a test db
    with patch("confluence_summarizer.database.DB_PATH", ":memory:"):
        init_db()
        yield

@pytest.fixture(autouse=True)
def mock_chroma():
    with patch("confluence_summarizer.services.rag._get_collection") as mock_col:
        mock_instance = MagicMock()
        mock_instance.query.return_value = {"documents": [["context1", "context2"]]}
        mock_col.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def mock_env():
    with patch.dict(os.environ, {"CONFLUENCE_URL": "http://test", "CONFLUENCE_USERNAME": "u", "CONFLUENCE_API_TOKEN": "t", "OPENAI_API_KEY": "sk-123", "CHROMA_DB_PATH": "test_db"}):
        yield

@pytest.mark.asyncio
async def test_database_operations(tmp_path):
    db_file = tmp_path / "test.db"
    with patch("confluence_summarizer.database.DB_PATH", str(db_file)):
        init_db()
        job = RefinementJob(page_id="p1", space_key="TEST")
        await save_job(job)

        fetched = await get_job("p1")
        assert fetched is not None
        assert fetched.page_id == "p1"
        assert fetched.status == RefinementStatus.PENDING

        job.status = RefinementStatus.COMPLETED
        job.analysis = AnalysisResult(critiques=[Critique(finding="f", severity="low", recommendation="r")], overall_quality="Good")
        await save_job(job)

        fetched2 = await get_job("p1")
        assert fetched2 is not None
        assert fetched2.status == RefinementStatus.COMPLETED
        assert fetched2.analysis is not None

        jobs = await get_jobs_by_space("TEST")
        assert len(jobs) == 1

@pytest.mark.asyncio
async def test_perform_refinement_success(mock_env):
    job = RefinementJob(page_id="p1", space_key="TEST")

    with patch("confluence_summarizer.main.get_page_content", return_value="Content"), \
         patch("confluence_summarizer.main.analyze", return_value=AnalysisResult(critiques=[], overall_quality="Good")), \
         patch("confluence_summarizer.main.rewrite", return_value="Rewritten"), \
         patch("confluence_summarizer.main.review", return_value=ReviewResult(status=RefinementStatus.COMPLETED, comments="Good")), \
         patch("confluence_summarizer.main.save_job") as mock_save:

         await _perform_refinement(job)
         assert job.status == RefinementStatus.COMPLETED
         assert job.refined_content == "Rewritten"
         assert mock_save.call_count > 0

@pytest.mark.asyncio
async def test_perform_refinement_failure(mock_env):
    job = RefinementJob(page_id="p1", space_key="TEST")

    with patch("confluence_summarizer.main.get_page_content", side_effect=Exception("API Error")), \
         patch("confluence_summarizer.main.save_job"):

         await _perform_refinement(job)
         assert job.status == RefinementStatus.FAILED
         assert "API Error" in job.error_message

@pytest.mark.asyncio
async def test_process_space(mock_env):
    with patch("confluence_summarizer.main.get_space_pages", return_value=[{"id": "1"}, {"id": "2"}]), \
         patch("confluence_summarizer.main.get_page_content", return_value="Content"), \
         patch("confluence_summarizer.main.ingest_page"), \
         patch("confluence_summarizer.main._perform_refinement"):

         await _process_space("TEST")

client = TestClient(app)

def test_api_refine_page():
    with patch("confluence_summarizer.main.get_job", return_value=None), \
         patch("confluence_summarizer.main.save_job"):
        response = client.post("/refine/123", json={"space_key": "TEST"})
        assert response.status_code == 200
        assert response.json() == {"message": "Refinement started.", "page_id": "123"}

def test_api_refine_space():
    response = client.post("/refine/space/TEST")
    assert response.status_code == 200

def test_api_get_status():
    with patch("confluence_summarizer.main.get_job", return_value=RefinementJob(page_id="123", space_key="TEST", status=RefinementStatus.COMPLETED)):
        response = client.get("/status/123")
        assert response.status_code == 200
        assert response.json()["status"] == "COMPLETED"

    with patch("confluence_summarizer.main.get_job", return_value=None):
        response = client.get("/status/404")
        assert response.status_code == 404

import pytest
import httpx
from httpx import ASGITransport
import sqlite3
import os

from confluence_summarizer.main import app
from confluence_summarizer.models import RefinementStatus
from confluence_summarizer.config import settings

@pytest.fixture(autouse=True)
def setup_db():
    # Force initialize the DB for tests
    conn = sqlite3.connect(settings.DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            page_id TEXT,
            space_key TEXT,
            error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    yield

    # Optional teardown
    if os.path.exists(settings.DB_PATH):
        try:
            os.remove(settings.DB_PATH)
            if os.path.exists(f"{settings.DB_PATH}-wal"):
                os.remove(f"{settings.DB_PATH}-wal")
            if os.path.exists(f"{settings.DB_PATH}-shm"):
                os.remove(f"{settings.DB_PATH}-shm")
        except Exception:
            pass


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_app_lifespan(client):
    response = await client.get("/status/dummy-job")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_job_flow(client, monkeypatch):
    from confluence_summarizer.database import get_job, update_job_status

    # Create job
    response = await client.post("/refine/12345")
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "PENDING"

    job_id = data["job_id"]

    # Check status
    response = await client.get(f"/status/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] in ["PENDING", "IN_PROGRESS", "FAILED", "COMPLETED"]

    # Manually update job to completed
    await update_job_status(job_id, RefinementStatus.COMPLETED)

    # Publish job
    response = await client.post(f"/publish/{job_id}")
    assert response.status_code == 200
    assert response.json() == {"message": "Job published successfully"}


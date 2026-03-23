import pytest
from httpx import AsyncClient, ASGITransport
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

    # Optional teardown: delete the db file to have clean state
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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_publish_not_completed_job(client, monkeypatch):
    from confluence_summarizer.database import create_job

    # Create an uncompleted job
    job = await create_job(page_id="123")

    response = await client.post(f"/publish/{job.job_id}")
    assert response.status_code == 400
    assert response.json()["detail"] == "Job is not completed"


@pytest.mark.asyncio
async def test_invalid_status_id(client):
    response = await client.get("/status/invalid-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"

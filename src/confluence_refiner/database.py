import sqlite3
import os
import asyncio
from typing import Optional
from .models import RefinementResult

DB_PATH = os.getenv("DB_PATH", "jobs.db")


def _init_db_sync():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            page_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


async def init_db():
    """Initializes the SQLite database asynchronously."""
    await asyncio.to_thread(_init_db_sync)


def _save_job_sync(job_json: str, page_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO jobs (page_id, data) VALUES (?, ?)
    """, (page_id, job_json))
    conn.commit()
    conn.close()


async def save_job(job: RefinementResult):
    """Saves a job to the database asynchronously."""
    job_json = job.model_dump_json()
    await asyncio.to_thread(_save_job_sync, job_json, job.page_id)


def _get_job_sync(page_id: str) -> Optional[str]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM jobs WHERE page_id = ?", (page_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None


async def get_job(page_id: str) -> Optional[RefinementResult]:
    """Retrieves a job from the database asynchronously."""
    data = await asyncio.to_thread(_get_job_sync, page_id)
    if data:
        return RefinementResult.model_validate_json(data)
    return None

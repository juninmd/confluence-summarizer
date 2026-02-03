import sqlite3
import asyncio
from typing import Optional
from contextlib import contextmanager
from .models import RefinementResult

DB_PATH = "jobs.db"


@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                page_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.commit()


def _save_job(job: RefinementResult):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        data = job.model_dump_json()
        cursor.execute("""
            INSERT OR REPLACE INTO jobs (page_id, data)
            VALUES (?, ?)
        """, (job.page_id, data))
        conn.commit()


def _get_job(page_id: str) -> Optional[RefinementResult]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM jobs WHERE page_id = ?", (page_id,))
        row = cursor.fetchone()

    if row:
        return RefinementResult.model_validate_json(row[0])
    return None


async def init_db():
    await asyncio.to_thread(_init_db)


async def save_job(job: RefinementResult):
    await asyncio.to_thread(_save_job, job)


async def get_job(page_id: str) -> Optional[RefinementResult]:
    return await asyncio.to_thread(_get_job, page_id)

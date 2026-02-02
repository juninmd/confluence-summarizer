import sqlite3
import asyncio
from typing import Optional
from .models import RefinementResult

DB_PATH = "jobs.db"


def _init_db():
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


def _save_job(job: RefinementResult):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    data = job.model_dump_json()
    cursor.execute("""
        INSERT OR REPLACE INTO jobs (page_id, data)
        VALUES (?, ?)
    """, (job.page_id, data))
    conn.commit()
    conn.close()


def _get_job(page_id: str) -> Optional[RefinementResult]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM jobs WHERE page_id = ?", (page_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return RefinementResult.model_validate_json(row[0])
    return None


async def init_db():
    await asyncio.to_thread(_init_db)


async def save_job(job: RefinementResult):
    await asyncio.to_thread(_save_job, job)


async def get_job(page_id: str) -> Optional[RefinementResult]:
    return await asyncio.to_thread(_get_job, page_id)

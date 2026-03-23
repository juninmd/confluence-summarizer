import asyncio
import sqlite3
import time
from typing import Optional
from uuid import uuid4

from confluence_summarizer.config import settings
from confluence_summarizer.models import JobStatus, RefinementStatus


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    conn = _get_connection()
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
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
    finally:
        conn.close()


async def init_db() -> None:
    await asyncio.to_thread(_init_db)


def _create_job(page_id: Optional[str] = None, space_key: Optional[str] = None) -> JobStatus:
    job_id = str(uuid4())
    now = time.time()
    job = JobStatus(
        job_id=job_id,
        status=RefinementStatus.PENDING,
        page_id=page_id,
        space_key=space_key,
        created_at=now,
        updated_at=now,
    )
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO jobs (job_id, status, page_id, space_key, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.job_id,
                job.status.value,
                job.page_id,
                job.space_key,
                job.error,
                job.created_at,
                job.updated_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return job


async def create_job(page_id: Optional[str] = None, space_key: Optional[str] = None) -> JobStatus:
    return await asyncio.to_thread(_create_job, page_id, space_key)


def _get_job(job_id: str) -> Optional[JobStatus]:
    conn = _get_connection()
    try:
        cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return JobStatus(
            job_id=row["job_id"],
            status=RefinementStatus(row["status"]),
            page_id=row["page_id"],
            space_key=row["space_key"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    finally:
        conn.close()


async def get_job(job_id: str) -> Optional[JobStatus]:
    return await asyncio.to_thread(_get_job, job_id)


def _update_job_status(job_id: str, status: RefinementStatus, error: Optional[str] = None) -> None:
    now = time.time()
    conn = _get_connection()
    try:
        conn.execute(
            """
            UPDATE jobs
            SET status = ?, error = COALESCE(?, error), updated_at = ?
            WHERE job_id = ?
            """,
            (status.value, error, now, job_id),
        )
        conn.commit()
    finally:
        conn.close()


async def update_job_status(job_id: str, status: RefinementStatus, error: Optional[str] = None) -> None:
    await asyncio.to_thread(_update_job_status, job_id, status, error)

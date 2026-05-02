import asyncio
import logging
import sqlite3
from typing import List, Optional

from src.confluence_summarizer.config import settings
from src.confluence_summarizer.models.domain import RefinementJob, RefinementStatus

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Initialize the SQLite database schema."""
    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                page_id TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                original_text TEXT,
                refined_text TEXT
            )
            """)
        conn.commit()


def save_job_sync(job: RefinementJob) -> None:
    """Save a job to the database synchronously.

    Args:
        job (RefinementJob): The refinement job object to save.

    Raises:
        ValueError: If id, page_id or status are missing or invalid.
    """
    if not job.id:
        raise ValueError("Job id is required")
    if not job.page_id:
        raise ValueError("Job page_id is required")
    if not job.status or type(job.status) is not RefinementStatus:
        raise ValueError("Job status must be a valid RefinementStatus")

    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, page_id, status, error, original_text, refined_text)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                error=excluded.error,
                original_text=excluded.original_text,
                refined_text=excluded.refined_text
            """,
            (
                job.id,
                job.page_id,
                job.status.value,
                job.error,
                job.original_text,
                job.refined_text,
            ),
        )
        conn.commit()


def save_jobs_bulk_sync(jobs: List[RefinementJob]) -> None:
    """Save multiple jobs to the database synchronously using a bulk operation.

    Args:
        jobs (List[RefinementJob]): The list of refinement job objects to save.
    """
    with sqlite3.connect(settings.DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO jobs (id, page_id, status, error, original_text, refined_text)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                error=excluded.error,
                original_text=excluded.original_text,
                refined_text=excluded.refined_text
            """,
            [
                (
                    job.id,
                    job.page_id,
                    job.status.value,
                    job.error,
                    job.original_text,
                    job.refined_text,
                )
                for job in jobs
            ],
        )
        conn.commit()


def get_job_sync(job_id: str) -> Optional[RefinementJob]:
    """Retrieve a job from the database synchronously.

    Args:
        job_id: The ID of the job to retrieve.

    Returns:
        The job data if found, or None.
    """
    with sqlite3.connect(settings.DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT id, page_id, status, error, original_text, refined_text FROM jobs WHERE id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        if row:
            return RefinementJob(
                id=row[0],
                page_id=row[1],
                status=RefinementStatus(row[2]),
                error=row[3],
                original_text=row[4],
                refined_text=row[5],
            )
        return None


async def save_job(job: RefinementJob) -> None:
    """Save a job asynchronously using asyncio.to_thread.

    Args:
        job: The refinement job object to save.
    """
    await asyncio.to_thread(save_job_sync, job)


async def get_job(job_id: str) -> Optional[RefinementJob]:
    """Get a job asynchronously using asyncio.to_thread.

    Args:
        job_id: The ID of the job to retrieve.

    Returns:
        The job data if found, or None.
    """
    return await asyncio.to_thread(get_job_sync, job_id)


async def save_jobs_bulk(jobs: List[RefinementJob]) -> None:
    """Save multiple jobs asynchronously using asyncio.to_thread.

    Args:
        jobs: The list of refinement job objects to save.
    """
    await asyncio.to_thread(save_jobs_bulk_sync, jobs)

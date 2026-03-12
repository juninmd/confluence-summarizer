import sqlite3
import json
import asyncio
from typing import Optional, List
from confluence_summarizer.models import RefinementJob

# The jobs database
DB_PATH = "jobs.db"


def init_db() -> None:
    """Initializes the SQLite database with WAL and NORMAL sync."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                page_id TEXT PRIMARY KEY,
                space_key TEXT NOT NULL,
                status TEXT NOT NULL,
                original_content TEXT,
                refined_content TEXT,
                analysis TEXT,
                review TEXT,
                error_message TEXT
            )
            """
        )
        conn.commit()


def _save_job_sync(job: RefinementJob) -> None:
    """Saves a job synchronously."""
    with sqlite3.connect(DB_PATH) as conn:
        analysis_json = job.analysis.model_dump_json() if job.analysis else None
        review_json = job.review.model_dump_json() if job.review else None

        conn.execute(
            """
            INSERT INTO jobs (page_id, space_key, status, original_content,
                refined_content, analysis, review, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                status=excluded.status,
                original_content=excluded.original_content,
                refined_content=excluded.refined_content,
                analysis=excluded.analysis,
                review=excluded.review,
                error_message=excluded.error_message
            """,
            (
                job.page_id,
                job.space_key,
                job.status.value,
                job.original_content,
                job.refined_content,
                analysis_json,
                review_json,
                job.error_message,
            ),
        )
        conn.commit()


async def save_job(job: RefinementJob) -> None:
    """Saves a job asynchronously."""
    await asyncio.to_thread(_save_job_sync, job)


def _get_job_sync(page_id: str) -> Optional[RefinementJob]:
    """Retrieves a job synchronously."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE page_id = ?", (page_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        # Convert back to dict and deserialize json
        data = dict(row)
        if data["analysis"]:
            data["analysis"] = json.loads(data["analysis"])
        if data["review"]:
            data["review"] = json.loads(data["review"])

        return RefinementJob(**data)


async def get_job(page_id: str) -> Optional[RefinementJob]:
    """Retrieves a job asynchronously."""
    return await asyncio.to_thread(_get_job_sync, page_id)


def _get_jobs_by_space_sync(space_key: str) -> List[RefinementJob]:
    """Retrieves all jobs for a space synchronously."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE space_key = ?", (space_key,))
        rows = cursor.fetchall()

        jobs: List[RefinementJob] = []
        for row in rows:
            data = dict(row)
            if data["analysis"]:
                data["analysis"] = json.loads(data["analysis"])
            if data["review"]:
                data["review"] = json.loads(data["review"])
            jobs.append(RefinementJob(**data))

        return jobs


async def get_jobs_by_space(space_key: str) -> List[RefinementJob]:
    """Retrieves all jobs for a space asynchronously."""
    return await asyncio.to_thread(_get_jobs_by_space_sync, space_key)

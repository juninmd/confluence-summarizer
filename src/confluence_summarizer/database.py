import sqlite3
import asyncio
from typing import Optional
from src.confluence_summarizer.config import settings
from src.confluence_summarizer.models.domain import JobRecord

def _get_connection() -> sqlite3.Connection:
    """Retorna uma conexão síncrona com o SQLite, configurada para WAL mode."""
    conn = sqlite3.connect(settings.db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Inicializa as tabelas do banco de dados (se não existirem)."""
    with _get_connection() as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                page_id TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT
            )
            '''
        )
        conn.commit()

async def create_job(job_id: str, page_id: str) -> None:
    """Cria assíncronamente um job no status PENDING."""
    def _create():
        with _get_connection() as conn:
            conn.execute(
                "INSERT INTO jobs (job_id, page_id, status) VALUES (?, ?, ?)",
                (job_id, page_id, "PENDING")
            )
            conn.commit()
    await asyncio.to_thread(_create)

async def update_job(job_id: str, status: str, result: Optional[str] = None, error: Optional[str] = None) -> None:
    """Atualiza o status e/ou detalhes de um job."""
    def _update():
        with _get_connection() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, result = COALESCE(?, result), error = COALESCE(?, error) WHERE job_id = ?",
                (status, result, error, job_id)
            )
            conn.commit()
    await asyncio.to_thread(_update)

async def get_job(job_id: str) -> Optional[JobRecord]:
    """Busca o estado atual de um job a partir de seu ID."""
    def _get() -> Optional[JobRecord]:
        with _get_connection() as conn:
            cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = cur.fetchone()
            if row:
                return JobRecord(**dict(row))
            return None
    return await asyncio.to_thread(_get)

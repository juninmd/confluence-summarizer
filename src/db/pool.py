"""Shared asyncpg connection pool for PostgreSQL/pgvector."""

import logging
from typing import Any, Optional, Sequence

import asyncpg

from src.config import settings
from src.db.schema import build_schema

logger = logging.getLogger(__name__)

# asyncpg ships partial type information; treat pool/connection objects as Any
_pool: Optional[Any] = None


def to_vector(values: Sequence[float]) -> str:
    """Serialize an embedding to the pgvector text literal, e.g. '[0.1,0.2]'."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


async def get_pool() -> Any:
    """Return the shared pool, creating it lazily on first use."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(  # pyright: ignore[reportUnknownMemberType]
            settings.DATABASE_URL, min_size=1, max_size=10
        )
    return _pool


async def init_pg() -> None:
    """Create the pool and ensure the schema (extension + tables) exists."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(build_schema())
    logger.info("PostgreSQL schema ready")


async def close_pg() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

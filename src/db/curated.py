"""Persistence of curated documents and their provenance."""

import json
from typing import Any, List, Optional

from src.curation.models import CuratedDoc, CurationStatus
from src.db.pool import get_pool


async def save_curated(doc: CuratedDoc) -> None:
    """Upsert a curated document and replace its source-page provenance."""
    conflicts = json.dumps([c.model_dump() for c in doc.conflicts])
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO curated_docs (id, space_key, title, markdown, status, conflicts, feedback)
                VALUES ($1, $2, $3, $4, $5, $6::text::jsonb, $7)
                ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title,
                    markdown = EXCLUDED.markdown, status = EXCLUDED.status,
                    conflicts = EXCLUDED.conflicts, feedback = EXCLUDED.feedback,
                    created_at = now()
                """,
                doc.id, doc.space_key, doc.title, doc.markdown, doc.status.value,
                conflicts, doc.feedback,
            )  # fmt: skip
            await conn.execute("DELETE FROM provenance WHERE curated_id = $1", doc.id)
            await conn.executemany(
                "INSERT INTO provenance (curated_id, page_id) VALUES ($1, $2)",
                [(doc.id, pid) for pid in doc.source_ids],
            )


async def get_status(curated_id: str) -> Optional[CurationStatus]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        value = await conn.fetchval(
            "SELECT status FROM curated_docs WHERE id = $1", curated_id
        )
    return CurationStatus(value) if value else None


async def get_curated(curated_id: str) -> Optional[CuratedDoc]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM curated_docs WHERE id = $1", curated_id
        )
        if row is None:
            return None
        sources = await conn.fetch(
            "SELECT page_id FROM provenance WHERE curated_id = $1 ORDER BY page_id",
            curated_id,
        )
    return CuratedDoc(
        id=row["id"], space_key=row["space_key"], title=row["title"],
        markdown=row["markdown"], status=CurationStatus(row["status"]),
        conflicts=json.loads(row["conflicts"]), feedback=row["feedback"],
        source_ids=[r["page_id"] for r in sources],
    )  # fmt: skip


async def list_curated(space_key: str, status: Optional[str] = None) -> List[Any]:
    """Summaries (id, title, status, conflict count) of a space's curated docs."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return list(
            await conn.fetch(
                "SELECT id, title, status, jsonb_array_length(conflicts) AS conflicts "
                "FROM curated_docs WHERE space_key = $1 AND ($2::text IS NULL OR status = $2) "
                "ORDER BY title",
                space_key, status,
            )  # fmt: skip
        )


async def set_status(curated_id: str, status: CurationStatus) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE curated_docs SET status = $2 WHERE id = $1",
            curated_id,
            status.value,
        )
    return result.endswith("1")

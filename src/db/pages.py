"""Persistence of backed-up pages, versions and attachments."""

import hashlib
from typing import Any, List, Sequence

from src.backup.models import AttachmentRecord, PageRecord
from src.db.pool import get_pool


def content_hash(body_storage: str) -> str:
    return hashlib.sha256(body_storage.encode("utf-8")).hexdigest()


async def save_page(
    page: PageRecord, markdown: str, path: str, attachments: Sequence[AttachmentRecord]
) -> None:
    """Upsert a page, record its version and replace its attachment rows."""
    digest = content_hash(page.body_storage)
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO pages (id, space_key, title, parent_id, version, url, labels,
                                   author, updated_at, body_storage, markdown, path, content_hash)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::text::timestamptz, $10, $11, $12, $13)
                ON CONFLICT (id) DO UPDATE SET
                    space_key = EXCLUDED.space_key, title = EXCLUDED.title,
                    parent_id = EXCLUDED.parent_id, version = EXCLUDED.version,
                    url = EXCLUDED.url, labels = EXCLUDED.labels, author = EXCLUDED.author,
                    updated_at = EXCLUDED.updated_at, body_storage = EXCLUDED.body_storage,
                    markdown = EXCLUDED.markdown, path = EXCLUDED.path, content_hash = EXCLUDED.content_hash,
                    deleted = false, backed_up_at = now()
                """,
                page.id, page.space_key, page.title, page.parent_id, page.version,
                page.url, page.labels, page.author, page.updated_at,
                page.body_storage, markdown, path, digest,
            )  # fmt: skip
            await conn.execute(
                "INSERT INTO page_versions (page_id, version, content_hash, body_storage) "
                "VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                page.id, page.version, digest, page.body_storage,
            )  # fmt: skip
            await conn.execute("DELETE FROM attachments WHERE page_id = $1", page.id)
            if attachments:
                await conn.executemany(
                    "INSERT INTO attachments (page_id, filename, sha256, media_type, "
                    "size_bytes, version, path) VALUES ($1, $2, $3, $4, $5, $6, $7)",
                    [
                        (
                            page.id,
                            a.filename,
                            a.sha256,
                            a.media_type,
                            a.size_bytes,
                            a.version,
                            a.path,
                        )
                        for a in attachments
                    ],
                )


async def list_space_pages(space_key: str) -> List[Any]:
    """Backed-up pages of a space (id, title, markdown, path, version, updated_at)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return list(
            await conn.fetch(
                "SELECT id, title, markdown, path, version, updated_at FROM pages "
                "WHERE space_key = $1 AND NOT deleted ORDER BY id",
                space_key,
            )
        )


async def mark_deleted(page_ids: Sequence[str]) -> None:
    """Flag pages removed from Confluence; keep the backup but drop them from the index."""
    if not page_ids:
        return
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "UPDATE pages SET deleted = true WHERE id = ANY($1)", list(page_ids)
            )
            await conn.execute(
                "DELETE FROM chunks WHERE page_id = ANY($1)", list(page_ids)
            )

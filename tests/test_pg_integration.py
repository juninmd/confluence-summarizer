"""Real PostgreSQL + pgvector round trip. Skipped when no database is reachable."""

import os
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from src.backup.models import AttachmentRecord, PageRecord
from src.config import settings
from src.curation.cluster import find_clusters
from src.curation.models import Conflict, CuratedDoc, CurationStatus
from src.db import curated, pages, pool
from src.models.domain import ConfluencePage
from src.services import rag

DIM = 4


def _admin_url() -> str:
    return settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"


async def _ensure_database() -> bool:
    name = settings.DATABASE_URL.rsplit("/", 1)[1]
    try:
        admin = await asyncpg.connect(_admin_url(), timeout=2)
    except Exception:
        return False
    try:
        if not await admin.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", name
        ):
            await admin.execute(f'CREATE DATABASE "{name}"')
        return True
    except Exception:
        return False
    finally:
        await admin.close()


def fake_embed(texts):
    """Deterministic 4-d vectors: topic words decide direction."""
    return [
        [1.0, 0.0, 0.0, 0.0] if "deploy" in t else [0.0, 1.0, 0.0, 0.0] for t in texts
    ]


@pytest.fixture
async def db(monkeypatch):
    if os.environ.get("SKIP_PG") or not await _ensure_database():
        pytest.skip("PostgreSQL not available")
    monkeypatch.setattr(settings, "EMBEDDING_DIM", DIM)
    try:
        await pool.init_pg()
    except Exception as exc:  # e.g. pgvector extension not installed
        await pool.close_pg()
        pytest.skip(f"pgvector unavailable: {exc}")
    p = await pool.get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "TRUNCATE chunks, pages, page_versions, attachments, provenance, curated_docs CASCADE"
        )
    yield
    await pool.close_pg()


@pytest.mark.asyncio
async def test_rag_ingest_query_and_reingest(db):
    with patch("src.services.rag.embed_texts", AsyncMock(side_effect=fake_embed)):
        await rag.ingest_page(
            ConfluencePage(id="1", title="a", space_key="S", body="como fazer deploy")
        )
        await rag.ingest_page(
            ConfluencePage(id="2", title="b", space_key="S", body="receita de bolo")
        )
        await rag.ingest_page(
            ConfluencePage(id="1", title="a", space_key="S", body="deploy v2")
        )
        assert await rag.query_context("deploy", n_results=1) == ["deploy v2"]
        assert (
            len(await rag.query_context("deploy", n_results=5)) == 2
        )  # re-ingest replaced, not duplicated


@pytest.mark.asyncio
async def test_pages_roundtrip_and_delete(db):
    page = PageRecord(
        id="1",
        title="T",
        space_key="S",
        version=2,
        body_storage="<p>x</p>",
        labels=["a"],
        updated_at="2024-01-01T10:00:00.000Z",
        author="Ana",
    )
    att = AttachmentRecord(
        filename="a.png", sha256="ab", size_bytes=3, path="assets/ab.png"
    )
    await pages.save_page(page, "md", "t-1/index.md", [att])
    await pages.save_page(page, "md2", "t-1/index.md", [])  # idempotent upsert
    rows = await pages.list_space_pages("S")
    assert [(r["id"], r["markdown"], r["version"]) for r in rows] == [("1", "md2", 2)]
    assert rows[0]["updated_at"].year == 2024
    await pages.mark_deleted(["1"])
    assert await pages.list_space_pages("S") == []


@pytest.mark.asyncio
async def test_find_clusters_groups_similar_pages(db):
    with patch("src.services.rag.embed_texts", AsyncMock(side_effect=fake_embed)):
        for pid, body in [("1", "deploy A"), ("2", "deploy B"), ("3", "bolo")]:
            await rag.ingest_page(
                ConfluencePage(id=pid, title=pid, space_key="S", body=body)
            )
    assert await find_clusters("S", ["1", "2", "3", "4"], 0.9) == [
        ["1", "2"],
        ["3"],
        ["4"],
    ]


@pytest.mark.asyncio
async def test_curated_docs_roundtrip(db):
    doc = CuratedDoc(
        id="c1",
        space_key="S",
        title="T",
        markdown="# T",
        status=CurationStatus.NEEDS_REVIEW,
        conflicts=[Conflict(topic="porta", needs_human=True)],
        source_ids=["2", "1"],
    )
    await curated.save_curated(doc)
    await curated.save_curated(
        doc.model_copy(update={"source_ids": ["1"]})
    )  # provenance replaced
    got = await curated.get_curated("c1")
    assert got and got.source_ids == ["1"] and got.conflicts[0].needs_human
    assert [
        r["conflicts"] for r in await curated.list_curated("S", "needs_review")
    ] == [1]
    assert await curated.list_curated("S", "approved") == []
    assert await curated.set_status("c1", CurationStatus.HUMAN_APPROVED)
    assert await curated.get_status("c1") == CurationStatus.HUMAN_APPROVED
    assert not await curated.set_status("nope", CurationStatus.APPROVED)

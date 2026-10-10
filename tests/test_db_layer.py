"""DB modules against a fake asyncpg pool (SQL shape + parameters)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backup.models import AttachmentRecord, PageRecord
from src.curation.models import Conflict, CuratedDoc, CurationStatus
from src.db import curated, pages, pool
from src.db.schema import build_schema
from src.services import embeddings
from tests.fakes import FakePool


@pytest.fixture
def conn():
    fake = FakePool()
    pool._pool = fake  # type: ignore[assignment]
    yield fake.conn
    pool._pool = None


def test_to_vector_and_schema(monkeypatch):
    assert pool.to_vector([1, 0.5]) == "[1.0,0.5]"
    from src.config import settings

    monkeypatch.setattr(settings, "EMBEDDING_DIM", 768)
    ddl = build_schema()
    assert (
        "vector(768)" in ddl
        and "USING hnsw" in ddl
        and "CREATE EXTENSION IF NOT EXISTS vector" in ddl
    )


@pytest.mark.asyncio
async def test_pool_lifecycle():
    fake = FakePool()
    fake.conn.execute = AsyncMock()  # type: ignore[method-assign]
    with patch(
        "src.db.pool.asyncpg.create_pool", AsyncMock(return_value=fake)
    ) as create:
        await pool.init_pg()
        assert await pool.get_pool() is fake
        create.assert_awaited_once()
    assert "CREATE EXTENSION" in fake.conn.execute.await_args.args[0]
    await pool.close_pg()
    assert pool._pool is None
    await pool.close_pg()  # idempotent


@pytest.mark.asyncio
async def test_save_page_upserts_everything(conn):
    page = PageRecord(
        id="1",
        title="T",
        space_key="S",
        version=2,
        body_storage="<p>x</p>",
        labels=["a"],
    )
    atts = [
        AttachmentRecord(
            filename="a.png", sha256="ab", size_bytes=3, path="assets/ab.png", version=1
        )
    ]
    await pages.save_page(page, "md", "t-1/index.md", atts)
    sql = conn.sql("execute")
    assert "ON CONFLICT (id) DO UPDATE" in sql[0] and "page_versions" in sql[1]
    assert "DELETE FROM attachments" in sql[2]
    assert conn.calls[0][2][10:13] == (
        "md",
        "t-1/index.md",
        pages.content_hash("<p>x</p>"),
    )
    assert conn.calls[-1][2][0][0][:3] == ("1", "a.png", "ab")
    conn.calls.clear()
    await pages.save_page(page, "md", "p", [])
    assert conn.sql("executemany") == []


@pytest.mark.asyncio
async def test_list_and_mark_deleted(conn):
    conn.rows = [{"id": "1"}]
    assert await pages.list_space_pages("S") == [{"id": "1"}]
    assert "NOT deleted" in conn.sql("fetch")[0]
    conn.calls.clear()
    await pages.mark_deleted([])
    assert conn.calls == []
    await pages.mark_deleted(["1", "2"])
    assert "UPDATE pages SET deleted = true" in conn.sql("execute")[0]
    assert "DELETE FROM chunks" in conn.sql("execute")[1]


def make_doc(**kw) -> CuratedDoc:
    base = dict(
        id="c1",
        space_key="S",
        title="T",
        markdown="# T",
        status=CurationStatus.NEEDS_REVIEW,
        conflicts=[Conflict(topic="x")],
        source_ids=["1", "2"],
    )
    return CuratedDoc(**{**base, **kw})


@pytest.mark.asyncio
async def test_curated_crud(conn):
    await curated.save_curated(make_doc())
    assert (
        conn.calls[0][2][4] == "needs_review" and '"topic": "x"' in conn.calls[0][2][5]
    )
    assert conn.sql("executemany") and conn.calls[-1][2][0] == [
        ("c1", "1"),
        ("c1", "2"),
    ]

    conn.value = "approved"
    assert await curated.get_status("c1") == CurationStatus.APPROVED
    conn.value = None
    assert await curated.get_status("c1") is None

    assert await curated.get_curated("c1") is None
    conn.rows = [
        {
            "id": "c1",
            "space_key": "S",
            "title": "T",
            "markdown": "m",
            "status": "approved",
            "conflicts": '[{"topic": "x"}]',
            "feedback": "f",
            "page_id": "1",
        }
    ]
    doc = await curated.get_curated("c1")
    assert doc and doc.conflicts[0].topic == "x" and doc.source_ids == ["1"]

    conn.rows = [{"id": "c1"}]
    assert await curated.list_curated("S", "needs_review") == [{"id": "c1"}]
    assert await curated.set_status("c1", CurationStatus.HUMAN_APPROVED) is True
    conn.result = "UPDATE 0"
    assert await curated.set_status("c1", CurationStatus.HUMAN_APPROVED) is False


@pytest.mark.asyncio
async def test_embed_texts_batches_in_order(monkeypatch):
    calls = []

    async def create(model, input):
        calls.append(len(input))
        return MagicMock(data=[MagicMock(embedding=[float(len(t))]) for t in input])

    client = MagicMock()
    client.embeddings.create = create
    monkeypatch.setattr(embeddings, "_client", client)
    texts = ["a" * (i % 5 + 1) for i in range(70)]
    vectors = await embeddings.embed_texts(texts)
    assert calls == [32, 32, 6] and vectors == [[float(len(t))] for t in texts]
    assert await embeddings.embed_texts([]) == []


def test_embeddings_client_uses_compatible_endpoint(monkeypatch):
    from src.config import settings

    monkeypatch.setattr(embeddings, "_client", None)
    monkeypatch.setattr(settings, "EMBEDDING_BASE_URL", "http://tei:8080/v1")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    client = embeddings._get_client()
    assert str(client.base_url).startswith("http://tei:8080/v1")
    assert embeddings._get_client() is client
    monkeypatch.setattr(embeddings, "_client", None)

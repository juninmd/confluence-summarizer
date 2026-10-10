"""PostgreSQL + pgvector schema (idempotent, safe to run on every startup)."""

from src.config import settings


def build_schema() -> str:
    """Return the DDL for all tables; the vector size follows EMBEDDING_DIM."""
    dim = int(settings.EMBEDDING_DIM)
    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pages (
    id TEXT PRIMARY KEY,
    space_key TEXT NOT NULL,
    title TEXT NOT NULL,
    parent_id TEXT,
    position INT NOT NULL DEFAULT 0,
    version INT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    labels TEXT[] NOT NULL DEFAULT '{{}}',
    author TEXT,
    updated_at TIMESTAMPTZ,
    body_storage TEXT NOT NULL,
    markdown TEXT NOT NULL,
    path TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL,
    deleted BOOLEAN NOT NULL DEFAULT false,
    backed_up_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pages_space_idx ON pages (space_key);

CREATE TABLE IF NOT EXISTS page_versions (
    page_id TEXT NOT NULL,
    version INT NOT NULL,
    content_hash TEXT NOT NULL,
    body_storage TEXT NOT NULL,
    PRIMARY KEY (page_id, version)
);

CREATE TABLE IF NOT EXISTS attachments (
    page_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    media_type TEXT NOT NULL DEFAULT '',
    size_bytes BIGINT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    path TEXT NOT NULL,
    PRIMARY KEY (page_id, filename)
);

CREATE TABLE IF NOT EXISTS chunks (
    page_id TEXT NOT NULL,
    chunk_index INT NOT NULL,
    space_key TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    embedding vector({dim}) NOT NULL,
    PRIMARY KEY (page_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS curated_docs (
    id TEXT PRIMARY KEY,
    space_key TEXT NOT NULL,
    title TEXT NOT NULL,
    markdown TEXT NOT NULL,
    status TEXT NOT NULL,
    conflicts JSONB NOT NULL DEFAULT '[]',
    feedback TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provenance (
    curated_id TEXT NOT NULL REFERENCES curated_docs (id) ON DELETE CASCADE,
    page_id TEXT NOT NULL,
    PRIMARY KEY (curated_id, page_id)
);
"""

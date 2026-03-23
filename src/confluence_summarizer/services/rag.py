import logging
import asyncio
from typing import List, Optional

import chromadb
from chromadb.api.types import Metadata
from chromadb.config import Settings as ChromaSettings

from confluence_summarizer.config import settings
from confluence_summarizer.models import PageData

logger = logging.getLogger(__name__)

_chroma_client: Optional[chromadb.ClientAPI] = None


def _get_client() -> chromadb.ClientAPI:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH, settings=ChromaSettings(anonymized_telemetry=False)
        )
    return _chroma_client


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        if end < text_length:
            # Try to break at a space
            last_space = text.rfind(" ", start, end)
            if last_space > start:
                end = last_space

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap
        if start < 0 or end == text_length:
            start = end

        # Avoid infinite loops for huge words without spaces
        if start <= end - chunk_size and start < text_length:
            start = end

    return chunks


def _ingest_page(page: PageData) -> None:
    client = _get_client()
    collection = client.get_or_create_collection("confluence_pages")

    try:
        # Delete old chunks for this page
        existing = collection.get(where={"page_id": page.page_id})
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
    except Exception as e:
        logger.warning(f"Error cleaning up old chunks for page {page.page_id}: {e}")

    chunks = chunk_text(page.content)
    if not chunks:
        return

    ids = [f"{page.page_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas: List[Metadata] = [
        {"page_id": page.page_id, "space_key": page.space_key, "title": page.title} for _ in chunks
    ]

    collection.add(documents=chunks, metadatas=metadatas, ids=ids)


async def ingest_page(page: PageData) -> None:
    await asyncio.to_thread(_ingest_page, page)


def _search(query: str, space_key: str, n_results: int = 3) -> List[str]:
    client = _get_client()
    try:
        collection = client.get_collection("confluence_pages")
    except Exception:
        return []

    results = collection.query(query_texts=[query], n_results=n_results, where={"space_key": space_key})

    if not results or not results["documents"] or not results["documents"][0]:
        return []

    return results["documents"][0]


async def search(query: str, space_key: str, n_results: int = 3) -> List[str]:
    return await asyncio.to_thread(_search, query, space_key, n_results)

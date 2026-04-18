import asyncio
import hashlib
import json
import logging
from typing import Any, List, Optional, cast

import chromadb
from chromadb.config import Settings as ChromaSettings
import redis.asyncio as redis

from src.confluence_summarizer.config import settings
from src.confluence_summarizer.models.domain import ConfluencePage

logger = logging.getLogger(__name__)

_chroma_client = None
_collection = None
_redis_client: Optional[redis.Redis] = None  # type: ignore


def _get_redis() -> Optional[redis.Redis]:  # type: ignore
    global _redis_client
    if _redis_client is None and settings.REDIS_URL:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _get_collection() -> Any:
    global _chroma_client, _collection
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_DB_PATH, settings=ChromaSettings(allow_reset=True)
        )
        _collection = _chroma_client.get_or_create_collection(
            name="confluence_pages", metadata={"hnsw:space": "cosine"}
        )
    return _collection


def chunk_text(text: str, max_chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Splits a long text into chunks with overlap.

    Args:
        text: The text to be split into chunks.
        max_chunk_size: Maximum size of each chunk.
        overlap: Number of characters to overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + max_chunk_size, text_len)

        # If we're not at the end of the text, try to find a word boundary
        if end < text_len:
            # Look for the last space character before the end
            last_space = text.rfind(" ", start, end)
            if last_space != -1 and last_space > start + overlap:
                end = last_space

        chunks.append(text[start:end].strip())

        # Move start forward, ensuring we make progress even with large words
        start = end - overlap
        if start <= 0 or end == text_len:
            start = end

    return [c for c in chunks if c]


def _ingest_page(page: ConfluencePage) -> None:
    """Synchronous function to ingest a single page into ChromaDB.

    Args:
        page: The Confluence page to ingest.
    """
    col = _get_collection()
    try:
        # First, delete existing chunks for this page to prevent duplication on re-ingestion
        col.delete(where={"page_id": page.id})
    except Exception as e:
        logger.warning(f"Failed to delete existing chunks for page {page.id}: {e}")

    chunks = chunk_text(page.body)
    if not chunks:
        return

    ids = [f"{page.id}_chunk_{i}" for i in range(len(chunks))]
    metadatas: List[Any] = [
        {
            "page_id": str(page.id),
            "title": str(page.title),
            "space_key": str(page.space_key),
            "chunk_index": i,
        }
        for i in range(len(chunks))
    ]

    # Type hinting workaround for ChromaDB metadatas
    col.add(documents=chunks, metadatas=metadatas, ids=ids)  # type: ignore


async def ingest_page(page: ConfluencePage) -> None:
    """Asynchronously ingest a page into ChromaDB using a thread pool.

    Args:
        page: The Confluence page to ingest.
    """
    await asyncio.to_thread(_ingest_page, page)


def _query_context(query_text: str, n_results: int = 5) -> List[str]:
    """Synchronous function to query ChromaDB for context.

    Args:
        query_text: The text query to search for.
        n_results: Number of results to return.

    Returns:
        A list of matching documents.
    """
    col = _get_collection()
    results = col.query(query_texts=[query_text], n_results=n_results)

    documents = results.get("documents", [])
    if documents and len(documents) > 0:
        return documents[
            0
        ]  # Return the first list of documents (for the single query text)
    return []


async def query_context(query_text: str, n_results: int = 5) -> List[str]:
    """Asynchronously query context from ChromaDB using a thread pool, with Redis caching.

    Args:
        query_text: The text query to search for.
        n_results: Number of results to return.

    Returns:
        A list of matching documents.
    """
    redis_client = _get_redis()
    cache_key: Optional[str] = None

    if redis_client:
        query_hash = hashlib.sha256(query_text.encode("utf-8")).hexdigest()
        cache_key = f"rag_query:{query_hash}:{n_results}"
        try:
            cached_result = await redis_client.get(cache_key)
            if cached_result:
                logger.info(f"RAG cache hit for query hash {query_hash}")
                return cast(List[str], json.loads(cached_result))
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")

    # Fallback to database
    results = await asyncio.to_thread(_query_context, query_text, n_results)

    if redis_client and cache_key is not None:
        try:
            # Cache for 1 hour, even empty results
            await redis_client.setex(cache_key, 3600, json.dumps(results))
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")

    return results

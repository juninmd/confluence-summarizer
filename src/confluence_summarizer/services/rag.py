"""
RAG Service
===========
Handles vector database interactions using ChromaDB.
Features:
- Document chunking with overlap
- Vector ingestion (upsert)
- Context retrieval (query)
"""

import os
import logging
import asyncio
from typing import List, Optional, Any, cast, Dict
import chromadb
from chromadb.api.types import OneOrMany, Metadata, Where
from ..models import ConfluencePage

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

logger = logging.getLogger(__name__)

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        # ChromaDB client initialization
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(name="confluence_pages")
    return _collection


async def init_rag():
    """Initializes the RAG service (ChromaDB connection) asynchronously."""
    await asyncio.to_thread(_get_collection)


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """
    Splits text into chunks with overlap, respecting word boundaries.
    """
    if not text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # If we are not at the end of the text, try to break at a space
        if end < text_len:
            segment = text[start:end]
            last_space = segment.rfind(' ')
            if last_space != -1:
                end = start + last_space

        # Ensure we move forward. If a word is longer than chunk_size, we split it.
        # The loop condition `start < text_len` and `end = min(...)` usually ensures progress,
        # but if `last_space` logic made `end` equal to `start` (e.g. space at index 0?), we fix it.
        if end <= start:
            end = min(start + chunk_size, text_len)

        # Extract chunk
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end == text_len:
            # Force loop termination naturally by setting start >= text_len
            start = text_len
            continue

        # Calculate next start position
        next_start = end - overlap
        # Ensure progress: strictly greater than current start
        start = max(start + 1, next_start)

    return chunks


def _ingest_page(page: ConfluencePage) -> None:
    """
    Ingests a page into the vector database.

    Args:
        page: The ConfluencePage object to ingest.
    """
    collection = _get_collection()

    # Delete existing entries for this page to avoid duplicates/stale chunks
    try:
        # We need to cast the dictionary to the Where type expected by ChromaDB
        where_clause = cast(Where, {"page_id": page.id})
        collection.delete(where=where_clause)
    except Exception as e:
        # Might fail if collection empty or other issues, but usually fine.
        logger.warning(f"Failed to delete existing chunks for page {page.id}: {e}")

    chunks = chunk_text(page.body)

    ids = [f"{page.id}_chunk_{i}" for i in range(len(chunks))]

    # Create metadata dictionaries
    metadatas_list: List[Dict[str, Any]] = [
        {
            "page_id": page.id,
            "title": page.title,
            "space_key": page.space_key,
            "url": page.url,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]

    # Cast to what Chroma expects
    metadatas = cast(OneOrMany[Metadata], metadatas_list)

    if chunks:
        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )


async def ingest_page(page: ConfluencePage) -> None:
    """
    Asynchronously ingests a page into the vector database.
    """
    await asyncio.to_thread(_ingest_page, page)


def _query_context(text: str, n_results: int = 3, exclude_page_id: Optional[str] = None) -> List[str]:
    """
    Retrieves relevant context for the given text.

    Args:
        text: The query text.
        n_results: Number of documents to retrieve.
        exclude_page_id: ID of the page to exclude from results.

    Returns:
        List[str]: A list of relevant document contents.
    """
    collection = _get_collection()

    where_filter: Optional[Where] = None
    if exclude_page_id:
        where_filter = cast(Where, {"page_id": {"$ne": exclude_page_id}})

    results = collection.query(
        query_texts=[text],
        n_results=n_results,
        where=where_filter
    )

    if results and results.get("documents"):
        # results['documents'] is a List[List[str]] (one list per query)
        docs = results["documents"]
        # Pyright sees docs[0] as List[Document] which is List[str]
        return docs[0]  # type: ignore

    return []


async def query_context(text: str, n_results: int = 3, exclude_page_id: Optional[str] = None) -> List[str]:
    """
    Asynchronously retrieves relevant context for the given text.
    """
    return await asyncio.to_thread(_query_context, text, n_results, exclude_page_id)

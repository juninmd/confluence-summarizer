import os
import asyncio
import logging
import chromadb
from typing import List, Any

logger = logging.getLogger(__name__)

# Path to local ChromaDB
DB_PATH = os.getenv("CHROMA_DB_PATH", "chroma_db")
_chroma_client: Any = None

def _get_client() -> Any:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=DB_PATH)
    return _chroma_client

def _get_collection() -> chromadb.Collection:
    """Returns the ChromaDB collection for Confluence documents."""
    client = _get_client()
    return client.get_or_create_collection("confluence_docs")

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Splits text into smaller chunks while respecting word boundaries and overlap."""
    chunks: List[str] = []
    if not text:
        return chunks

    i = 0
    while i < len(text):
        if len(text) - i <= chunk_size:
            chunks.append(text[i:])
            break

        end_idx = i + chunk_size
        while end_idx > i and text[end_idx - 1] not in (' ', '\n', '\t'):
            end_idx -= 1

        if end_idx == i:
            end_idx = i + chunk_size

        chunks.append(text[i:end_idx])
        i = end_idx - overlap
        if i <= end_idx - chunk_size:
            i = end_idx

    return chunks

def _ingest_page(page_id: str, space_key: str, content: str) -> None:
    """Synchronously ingests a single page's content into ChromaDB."""
    collection = _get_collection()

    try:
        # Delete old chunks for the page
        collection.delete(where={"page_id": page_id})
    except Exception as e:
        logger.warning(f"Failed to delete old chunks for page {page_id}: {e}")

    chunks = chunk_text(content)
    if not chunks:
        return

    ids = [f"{page_id}_{i}" for i in range(len(chunks))]
    metadatas = [{"page_id": page_id, "space_key": space_key, "chunk_index": i} for i in range(len(chunks))]
    # Cast to proper list for chroma DB
    meta_list = [dict(m) for m in metadatas]

    collection.add(
        documents=chunks,
        metadatas=meta_list,  # type: ignore
        ids=ids
    )

async def ingest_page(page_id: str, space_key: str, content: str) -> None:
    """Asynchronously ingests a single page's content into ChromaDB."""
    await asyncio.to_thread(_ingest_page, page_id, space_key, content)

def _query_context(query: str, n_results: int = 5) -> List[str]:
    """Synchronously queries ChromaDB for context related to a query."""
    collection = _get_collection()
    results = collection.query(query_texts=[query], n_results=n_results)

    if not results or not results["documents"] or len(results["documents"]) == 0 or not results["documents"][0]:
        return []

    # Cast elements to strings
    docs = results["documents"][0]
    return [str(doc) for doc in docs if doc is not None]  # type: ignore

async def query_context(query: str, n_results: int = 5) -> List[str]:
    """Asynchronously queries ChromaDB for context related to a query."""
    return await asyncio.to_thread(_query_context, query, n_results)

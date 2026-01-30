import os
from typing import List, Optional
import chromadb
from ..models import ConfluencePage

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        # ChromaDB client initialization
        _client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        _collection = _client.get_or_create_collection(name="confluence_pages")
    return _collection


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """
    Splits text into chunks with overlap.
    """
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunks.append(text[start:end])
        if end == text_len:
            break
        start += chunk_size - overlap

    return chunks


def ingest_page(page: ConfluencePage) -> None:
    """
    Ingests a page into the vector database.

    Args:
        page: The ConfluencePage object to ingest.
    """
    collection = _get_collection()

    # Delete existing entries for this page to avoid duplicates/stale chunks
    try:
        collection.delete(where={"page_id": page.id})
    except Exception:
        # Might fail if collection empty or other issues, but usually fine.
        pass

    chunks = chunk_text(page.body)

    ids = [f"{page.id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "page_id": page.id,
            "title": page.title,
            "space_key": page.space_key,
            "url": page.url,
            "chunk_index": i
        }
        for i in range(len(chunks))
    ]

    if chunks:
        collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas
        )


def query_context(text: str, n_results: int = 3, exclude_page_id: Optional[str] = None) -> List[str]:
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

    where_filter = None
    if exclude_page_id:
        where_filter = {"page_id": {"$ne": exclude_page_id}}

    results = collection.query(
        query_texts=[text],
        n_results=n_results,
        where=where_filter
    )

    if results and results.get("documents"):
        # results['documents'] is a List[List[str]] (one list per query)
        return results["documents"][0]  # type: ignore
    return []

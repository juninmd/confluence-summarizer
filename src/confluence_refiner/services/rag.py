import os
from typing import List
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


def ingest_page(page: ConfluencePage) -> None:
    """
    Ingests a page into the vector database.

    Args:
        page: The ConfluencePage object to ingest.
    """
    collection = _get_collection()
    # In a real scenario, we would split the text into chunks.
    # Here we upsert the whole body, assuming it fits the model's context or is truncated.
    collection.upsert(
        ids=[page.id],
        documents=[page.body],
        metadatas=[{"title": page.title, "space_key": page.space_key, "url": page.url}]
    )


def query_context(text: str, n_results: int = 3) -> List[str]:
    """
    Retrieves relevant context for the given text.

    Args:
        text: The query text.
        n_results: Number of documents to retrieve.

    Returns:
        List[str]: A list of relevant document contents.
    """
    collection = _get_collection()
    results = collection.query(
        query_texts=[text],
        n_results=n_results
    )

    if results and results.get("documents"):
        # results['documents'] is a List[List[str]] (one list per query)
        return results["documents"][0]  # type: ignore
    return []

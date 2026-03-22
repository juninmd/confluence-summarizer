import asyncio
import logging
from typing import List, Optional
import chromadb
from chromadb.api import ClientAPI
from src.confluence_summarizer.config import settings

logger = logging.getLogger(__name__)

_chroma_client: Optional[ClientAPI] = None

def _get_client() -> ClientAPI:
    """Retorna um singleton de ChromaDB configurado em settings para evitar locações concorrentes do SQLite."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_db_path)
    return _chroma_client

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Divide um texto em chunks respeitando sobreposições seguras sem infinitos loops."""
    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        if end >= text_len:
            chunks.append(text[start:])
            break

        # Tenta quebrar em limites de palavras (espaços) voltando o índice de trás pra frente
        space_idx = text.rfind(" ", start, end)
        if space_idx != -1 and space_idx > start:
             end = space_idx

        chunks.append(text[start:end])
        # Avança respeitando o overlap pra garantir contexto fluido
        start = end - overlap

    return chunks

async def ingest_page(page_id: str, content: str, title: str) -> None:
    """Ingere assincronamente os chunks de uma página HTML crua do Confluence no ChromaDB."""
    def _ingest():
        client = _get_client()
        collection = client.get_or_create_collection("confluence_docs")

        # Deleta chunks existentes para não duplicar informações e logs catch warning
        try:
            collection.delete(where={"page_id": page_id})
        except Exception as e:
            logger.warning(f"Erro ao tentar limpar page_id {page_id} do ChromaDB: {e}")

        chunks = chunk_text(content)

        if not chunks:
             return

        ids = [f"{page_id}_{i}" for i in range(len(chunks))]
        # Metadata requires explicit dict cast to avoid database types mismatch
        from chromadb.api.types import Metadata
        metadatas: List[Metadata] = [
            {"page_id": page_id, "title": title, "chunk_index": i}
            for i in range(len(chunks))
        ]

        collection.add(
            documents=chunks,
            metadatas=metadatas,
            ids=ids
        )
    await asyncio.to_thread(_ingest)

async def query_context(query_text: str, n_results: int = 3) -> List[str]:
    """Busca trechos do repositório vetorizado para verificação cruzada (cross-checking)."""
    def _query() -> List[str]:
        client = _get_client()
        collection = client.get_or_create_collection("confluence_docs")

        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )

        # Results docs returns a list of list
        documents = results.get("documents")
        if documents and len(documents) > 0:
             return list(documents[0])
        return []

    return await asyncio.to_thread(_query)

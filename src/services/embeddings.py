"""Embedding client for any OpenAI-compatible endpoint (TEI, vLLM, Ollama)."""

from typing import List, Optional

from openai import AsyncOpenAI

from src.config import settings

_BATCH_SIZE = 32
_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
            # Local servers ignore the key but the SDK requires a non-empty one
            api_key=settings.OPENAI_API_KEY or "not-needed",
            max_retries=2,
        )
    return _client


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed texts in batches, preserving input order."""
    client = _get_client()
    vectors: List[List[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL, input=batch
        )
        vectors.extend(item.embedding for item in response.data)
    return vectors

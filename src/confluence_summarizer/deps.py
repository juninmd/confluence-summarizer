import asyncio
import secrets
from typing import Any

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.confluence_summarizer.config import settings

# Concurrency limits for background tasks
refinement_semaphore = asyncio.Semaphore(settings.REFINEMENT_CONCURRENCY)
ingestion_semaphore = asyncio.Semaphore(settings.INGESTION_CONCURRENCY)

# Store background tasks to prevent garbage collection
background_tasks_set: set[asyncio.Task[Any]] = set()

limiter = Limiter(key_func=get_remote_address)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(api_key_header: str | None = Security(api_key_header)) -> str:
    """Validate and return the API key from the request header."""
    if not api_key_header or not secrets.compare_digest(
        api_key_header, settings.APP_API_KEY
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return api_key_header

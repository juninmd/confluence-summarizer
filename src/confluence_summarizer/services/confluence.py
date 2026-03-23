import logging
import urllib.parse
from typing import Any, AsyncGenerator, Dict, Optional, Tuple

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from confluence_summarizer.config import settings
from confluence_summarizer.models import PageData

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


def _get_auth() -> Optional[Tuple[str, str]]:
    if (
        not settings.CONFLUENCE_USERNAME
        or not settings.CONFLUENCE_API_TOKEN
        or settings.CONFLUENCE_API_TOKEN == "dummy"
    ):
        logger.warning("Missing Confluence credentials. Auth will not be used.")
        return None
    return (settings.CONFLUENCE_USERNAME, settings.CONFLUENCE_API_TOKEN)


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        logger.warning("Shared Confluence client not initialized, falling back to a temporary client.")
        return httpx.AsyncClient(timeout=30.0)
    return _client


async def init_client() -> None:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_page(page_id: str) -> PageData:
    client = _get_client()
    url = f"{settings.CONFLUENCE_URL}/wiki/api/v2/pages/{urllib.parse.quote(page_id)}?body-format=storage"
    auth = _get_auth()
    response = await client.get(url, auth=auth)
    response.raise_for_status()
    data = response.json()

    return PageData(
        page_id=str(data["id"]),
        space_key=data.get("spaceId", ""),  # Confluence v2 returns spaceId instead of space_key for this endpoint
        title=data["title"],
        content=data.get("body", {}).get("storage", {}).get("value", ""),
        version=data.get("version", {}).get("number", 1),
    )


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_pages_in_space(space_key: str) -> AsyncGenerator[PageData, None]:
    client = _get_client()
    auth = _get_auth()
    # Confluence API v2 uses a different approach. First we might need the space ID, but let's assume space_key is accepted by some endpoint or we search.
    # To keep it simple, we'll use the v1 API for space pages since it's easier to paginate by space key
    base_url = f"{settings.CONFLUENCE_URL}/wiki/rest/api/content"
    params: Dict[str, Any] = {
        "spaceKey": urllib.parse.quote(space_key),
        "expand": "body.storage,version",
        "limit": 50,
        "start": 0,
    }

    while True:
        response = await client.get(base_url, params=params, auth=auth)
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])
        if not results:
            break

        for result in results:
            yield PageData(
                page_id=str(result["id"]),
                space_key=space_key,
                title=result["title"],
                content=result.get("body", {}).get("storage", {}).get("value", ""),
                version=result.get("version", {}).get("number", 1),
            )

        if "next" not in data.get("_links", {}):
            break

        params["start"] += params["limit"]

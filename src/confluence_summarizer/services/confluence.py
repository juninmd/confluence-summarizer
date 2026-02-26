"""
Confluence Service
==================
Handles all interactions with the Atlassian Confluence API.
Features:
- Authentication management
- Asynchronous HTTP requests
- Pagination handling
- Rate limit handling with exponential backoff (tenacity)
"""

import os
import logging
from typing import List, Any, cast, Optional, Tuple
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from ..models import ConfluencePage

# Configuration from environment variables
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "https://example.atlassian.net/wiki")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME", "")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


def _get_auth() -> Optional[Tuple[str, str]]:
    """
    Retrieves the authentication tuple for Confluence.

    Returns:
        Optional[tuple[str, str]]: (username, api_token) or None if not configured.
    """
    if not CONFLUENCE_USERNAME or not CONFLUENCE_API_TOKEN:
        logger.warning("Confluence credentials not set. API calls may fail.")
        return None
    return (CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN)


def init_client() -> None:
    """
    Initializes the global HTTP client for connection pooling.
    Should be called at application startup.
    """
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30.0)


async def close_client():
    """Closes the global HTTP client."""
    global _client
    if _client:
        await _client.aclose()
        _client = None


def _get_client() -> httpx.AsyncClient:
    """Returns the shared HTTP client or creates a temporary one if not initialized."""
    if _client:
        return _client
    # Fallback/Warning: This shouldn't ideally happen in prod if lifecycle is managed correctly
    logger.warning("Using fallback HTTP client - init_client() might not have been called.")
    return httpx.AsyncClient(timeout=30.0)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_page(page_id: str) -> ConfluencePage:
    """
    Fetches a single page from Confluence by its ID.

    Args:
        page_id: The ID of the page to fetch.

    Returns:
        ConfluencePage: The page model.

    Raises:
        httpx.HTTPStatusError: If the API request fails.
    """
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}"
    params = {"expand": "body.storage,version,space"}

    client = _get_client()
    # If the client is the shared one, we don't close it here.
    # If it's a temporary one (fallback), we should technically close it, but
    # to keep it simple and performant, we assume init_client() is called.
    # For safety in fallback:
    should_close = client is not _client

    try:
        response = await client.get(
            url,
            auth=_get_auth(),
            headers={"Accept": "application/json"},
            params=params
        )
        response.raise_for_status()
        data = response.json()

        space_key = data.get("space", {}).get("key", "UNKNOWN")
        webui = data.get("_links", {}).get("webui", "")

        return ConfluencePage(
            id=data["id"],
            title=data["title"],
            body=data["body"]["storage"]["value"],
            space_key=space_key,
            version=data["version"]["number"],
            url=f"{CONFLUENCE_URL}{webui}"
        )
    finally:
        if should_close:
            await client.aclose()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_pages_from_space(
    space_key: str,
    limit: Optional[int] = None,
    page_size: int = 50
) -> List[ConfluencePage]:
    """
    Fetches all pages from a given space, handling pagination.

    Args:
        space_key: The key of the Confluence space.
        limit: Max pages to fetch. If None, fetches all pages.
        page_size: Number of items requested per API call (max 50 in Confluence Cloud).

    Returns:
        List[ConfluencePage]: List of pages found.
    """
    url = f"{CONFLUENCE_URL}/rest/api/content"
    base_params = {
        "spaceKey": space_key,
        "type": "page",
        "expand": "body.storage,version,space",
        "limit": max(1, min(page_size, 50))
    }

    pages: List[ConfluencePage] = []
    start = 0

    client = _get_client()
    should_close = client is not _client

    try:
        while limit is None or len(pages) < limit:
            current_params = base_params.copy()
            current_params["start"] = start

            response = await client.get(
                url,
                auth=_get_auth(),
                headers={"Accept": "application/json"},
                params=current_params
            )
            response.raise_for_status()
            data = response.json()

            results = data.get("results", [])
            if not results:
                break

            for item in results:
                webui = item.get("_links", {}).get("webui", "")
                page = ConfluencePage(
                    id=item["id"],
                    title=item["title"],
                    body=item["body"]["storage"]["value"],
                    space_key=space_key,
                    version=item["version"]["number"],
                    url=f"{CONFLUENCE_URL}{webui}"
                )
                pages.append(page)
                if limit is not None and len(pages) >= limit:
                    break

            # Check for next page
            if "_links" not in data or "next" not in data["_links"]:
                break

            start += len(results)
    finally:
        if should_close:
            await client.aclose()

    return pages


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def update_page(page_id: str, title: str, body: str, version_number: int) -> ConfluencePage:
    """
    Updates a Confluence page with new content.

    Args:
        page_id: The ID of the page to update.
        title: The new title of the page.
        body: The new storage format body.
        version_number: The current version number (will be incremented).

    Returns:
        ConfluencePage: The updated page model.
    """
    url = f"{CONFLUENCE_URL}/rest/api/content/{page_id}"

    payload = {
        "id": page_id,
        "type": "page",
        "title": title,
        "body": {
            "storage": {
                "value": body,
                "representation": "storage"
            }
        },
        "version": {
            "number": version_number + 1
        }
    }

    client = _get_client()
    should_close = client is not _client

    try:
        response = await client.put(
            url,
            auth=cast(Any, _get_auth()),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json=payload
        )
        response.raise_for_status()
        data = response.json()

        space_key = data.get("space", {}).get("key", "UNKNOWN")
        webui = data.get("_links", {}).get("webui", "")

        return ConfluencePage(
            id=data["id"],
            title=data["title"],
            body=data["body"]["storage"]["value"],
            space_key=space_key,
            version=data["version"]["number"],
            url=f"{CONFLUENCE_URL}{webui}"
        )
    finally:
        if should_close:
            await client.aclose()

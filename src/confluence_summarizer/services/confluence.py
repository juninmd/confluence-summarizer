import os
import logging
from typing import Optional, List, Dict, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


def init_client() -> None:
    """Initializes the shared HTTP client."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient()


async def close_client() -> None:
    """Closes the shared HTTP client."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get_auth() -> Optional[tuple[str, str]]:
    """Retrieves authentication credentials from environment variables."""
    username = os.getenv("CONFLUENCE_USERNAME")
    api_token = os.getenv("CONFLUENCE_API_TOKEN")

    if not username or not api_token:
        logger.warning("Confluence credentials (CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN) are missing.")
        return None

    return (username, api_token)


def _get_client_instance() -> httpx.AsyncClient:
    """Gets the shared client instance, returning a temporary one if uninitialized."""
    if _client is None:
        logger.warning("Shared HTTP client is not initialized. Falling back to a temporary client.")
        return httpx.AsyncClient()
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_page_content(page_id: str) -> str:
    """Retrieves the content of a specific Confluence page."""
    base_url = os.getenv("CONFLUENCE_URL", "").rstrip("/")
    if not base_url:
        logger.error("CONFLUENCE_URL is not set.")
        raise ValueError("CONFLUENCE_URL is required.")

    url = f"{base_url}/wiki/api/v2/pages/{page_id}?body-format=storage"
    auth = _get_auth()

    client = _get_client_instance()
    try:
        response = await client.get(url, auth=auth)
        response.raise_for_status()
        data = response.json()
        body = data.get("body", {}).get("storage", {}).get("value", "")
        return str(body)
    finally:
        # If we fell back to a temporary client, close it to avoid resource leaks.
        if _client is None:
            await client.aclose()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_space_pages(space_key: str) -> List[Dict[str, Any]]:
    """Retrieves all pages in a given space, handling pagination."""
    base_url = os.getenv("CONFLUENCE_URL", "").rstrip("/")
    if not base_url:
        logger.error("CONFLUENCE_URL is not set.")
        raise ValueError("CONFLUENCE_URL is required.")

    all_pages: List[Dict[str, Any]] = []
    # Paginate in chunks of 50
    url: Optional[str] = f"{base_url}/wiki/api/v2/spaces/{space_key}/pages?limit=50"
    auth = _get_auth()
    client = _get_client_instance()

    try:
        while url:
            response = await client.get(url, auth=auth)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            all_pages.extend(results)

            links = data.get("_links", {})
            next_link = links.get("next")
            url = f"{base_url}{next_link}" if next_link else None

        return all_pages
    finally:
        if _client is None:
            await client.aclose()

import logging
import urllib.parse
from typing import Any, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.models.domain import ConfluencePage

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


def is_transient_error(exc: BaseException) -> bool:
    """Retry network failures, 429 and 5xx; 4xx (404, 401...) will fail again."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, httpx.RequestError)


def _get_auth() -> Optional[tuple[str, str]]:
    if not settings.CONFLUENCE_USERNAME or not settings.CONFLUENCE_API_TOKEN:
        logger.warning("Confluence credentials are not set. API calls will fail.")
        return None
    return (settings.CONFLUENCE_USERNAME, settings.CONFLUENCE_API_TOKEN)


async def init_client() -> None:
    global _client
    if _client is None:
        auth = _get_auth()
        _client = httpx.AsyncClient(
            base_url=settings.CONFLUENCE_URL,
            auth=auth if auth else None,
            timeout=httpx.Timeout(30.0),
            headers={"Accept": "application/json"},
        )


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        logger.warning(
            "Confluence client is not initialized. Falling back to an unmanaged client."
        )
        auth = _get_auth()
        return httpx.AsyncClient(
            base_url=settings.CONFLUENCE_URL,
            auth=auth if auth else None,
            timeout=httpx.Timeout(30.0),
            headers={"Accept": "application/json"},
        )
    return _client


def clean_html(html_content: str) -> str:
    # Just return raw HTML to preserve structure for the agents
    return html_content


_retry_transient = retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception(is_transient_error),
)


@_retry_transient
async def _get_json(url: str) -> Any:
    response = await _get_client().get(url)
    response.raise_for_status()
    return response.json()


def _to_page(item: Any, space_key: str) -> ConfluencePage:
    body = ""
    if "body" in item and "storage" in item["body"]:
        body = clean_html(item["body"]["storage"].get("value", ""))
    webui = item.get("_links", {}).get("webui", "")
    return ConfluencePage(
        id=str(item["id"]),
        title=item["title"],
        space_key=space_key,
        body=body,
        version=item.get("version", {}).get("number", 1),
        url=f"{settings.CONFLUENCE_URL}{webui}" if webui else "",
    )


async def get_page(page_id: str) -> ConfluencePage:
    # Confluence API v1 to ensure space_key is available as expected
    safe_page_id = urllib.parse.quote(page_id)
    data = await _get_json(
        f"/wiki/rest/api/content/{safe_page_id}?expand=body.storage,space,version"
    )
    return _to_page(data, data.get("space", {}).get("key", "unknown"))


async def get_pages_from_space(
    space_key: str, limit: Optional[int] = None, page_size: int = 50
) -> List[ConfluencePage]:
    # Retries wrap each request, so a transient error on page N does not
    # refetch pages 1..N-1.
    pages: List[ConfluencePage] = []
    safe_space_key = urllib.parse.quote(space_key)
    url = f"/wiki/rest/api/content?spaceKey={safe_space_key}&expand=body.storage,version&limit={page_size}"

    while url:
        data = await _get_json(url)
        for item in data.get("results", []):
            pages.append(_to_page(item, space_key))
            if limit and len(pages) >= limit:
                return pages

        next_link = data.get("_links", {}).get("next")
        # The next link might be a relative path without /wiki
        url = (
            ""
            if not next_link
            else next_link
            if next_link.startswith("/wiki")
            else f"/wiki{next_link}"
        )

    return pages


@_retry_transient
async def update_page(page_id: str, title: str, body: str, version_number: int) -> Any:
    """Publish a new version of the page back to Confluence.

    Args:
        page_id (str): The ID of the page to update.
        title (str): The new title of the page.
        body (str): The new body content.
        version_number (int): The next version number for the update.

    Returns:
        Any: The JSON response from the Confluence API.
    """
    client = _get_client()
    payload = {
        "id": page_id,
        "status": "current",
        "title": title,
        "body": {"representation": "storage", "value": body},
        "version": {"number": version_number},
    }
    # Using v2 API for updates
    safe_page_id = urllib.parse.quote(page_id)
    response = await client.put(f"/wiki/api/v2/pages/{safe_page_id}", json=payload)
    response.raise_for_status()
    return response.json()

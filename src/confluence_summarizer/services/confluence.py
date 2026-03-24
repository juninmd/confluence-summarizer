import logging
from typing import Any, List, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.confluence_summarizer.config import settings
from src.confluence_summarizer.models.domain import ConfluencePage

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


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


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
)
async def get_page(page_id: str) -> ConfluencePage:
    client = _get_client()
    # Confluence API v1 to ensure space_key is available as expected
    response = await client.get(
        f"/wiki/rest/api/content/{page_id}?expand=body.storage,space"
    )
    response.raise_for_status()
    data = response.json()

    body = ""
    if "body" in data and "storage" in data["body"]:
        body = clean_html(data["body"]["storage"].get("value", ""))

    space_key = "unknown"
    if "space" in data and "key" in data["space"]:
        space_key = data["space"]["key"]

    version = data.get("version", {}).get("number", 1)
    webui = data.get("_links", {}).get("webui", "")
    page_url = f"{settings.CONFLUENCE_URL}{webui}" if webui else ""

    return ConfluencePage(
        id=str(data["id"]),
        title=data["title"],
        space_key=space_key,
        body=body,
        version=version,
        url=page_url,
    )


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
)
async def get_pages_from_space(
    space_key: str, limit: Optional[int] = None, page_size: int = 50
) -> List[ConfluencePage]:
    client = _get_client()
    pages: List[ConfluencePage] = []

    url = f"/wiki/rest/api/content?spaceKey={space_key}&expand=body.storage,version&limit={page_size}"

    while url:
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        for item in data.get("results", []):
            body = ""
            if "body" in item and "storage" in item["body"]:
                body = clean_html(item["body"]["storage"].get("value", ""))

            version = item.get("version", {}).get("number", 1)
            webui = item.get("_links", {}).get("webui", "")
            page_url = f"{settings.CONFLUENCE_URL}{webui}" if webui else ""

            pages.append(
                ConfluencePage(
                    id=str(item["id"]),
                    title=item["title"],
                    space_key=space_key,
                    body=body,
                    version=version,
                    url=page_url,
                )
            )

            if limit and len(pages) >= limit:
                return pages[:limit]

        links = data.get("_links", {})
        if "next" in links:
            # The next link might be a relative path without /wiki
            next_link = links["next"]
            url = next_link if next_link.startswith("/wiki") else f"/wiki{next_link}"
        else:
            url = ""

    return pages


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
)
async def update_page(page_id: str, title: str, body: str, version_number: int) -> Any:
    """Publish a new version of the page back to Confluence.
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
    payload = {
        "id": page_id,
        "status": "current",
        "title": title,
        "body": {"representation": "storage", "value": body},
        "version": {"number": version_number},
    }
    # Using v2 API for updates
    response = await client.put(f"/wiki/api/v2/pages/{page_id}", json=payload)
    response.raise_for_status()
    return response.json()

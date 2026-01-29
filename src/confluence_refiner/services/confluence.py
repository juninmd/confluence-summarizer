import os
from typing import List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from ..models import ConfluencePage

# Configuration from environment variables
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "https://example.atlassian.net/wiki")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME", "")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN", "")


def _get_auth():
    if not CONFLUENCE_USERNAME or not CONFLUENCE_API_TOKEN:
        return None
    return (CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN)


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

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            auth=_get_auth(),
            headers={"Accept": "application/json"},
            params=params,
            timeout=10.0
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


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def get_pages_from_space(space_key: str, limit: int = 50) -> List[ConfluencePage]:
    """
    Fetches all pages from a given space, handling pagination.

    Args:
        space_key: The key of the Confluence space.
        limit: Max pages to fetch.

    Returns:
        List[ConfluencePage]: List of pages found.
    """
    url = f"{CONFLUENCE_URL}/rest/api/content"
    base_params = {
        "spaceKey": space_key,
        "type": "page",
        "expand": "body.storage,version,space",
        "limit": min(limit, 25)  # Fetch in chunks
    }

    pages: List[ConfluencePage] = []
    start = 0

    async with httpx.AsyncClient() as client:
        while len(pages) < limit:
            current_params = base_params.copy()
            current_params["start"] = start

            response = await client.get(
                url,
                auth=_get_auth(),
                headers={"Accept": "application/json"},
                params=current_params,
                timeout=20.0
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
                if len(pages) >= limit:
                    break

            # Check for next page
            if "_links" not in data or "next" not in data["_links"]:
                break

            start += len(results)

    return pages

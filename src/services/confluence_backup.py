"""Confluence read APIs used by the backup: content listing, attachments, downloads."""

import urllib.parse
from typing import Any, AsyncIterator, Dict, List

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.services.confluence import _get_client  # pyright: ignore[reportPrivateUsage]

_retry = retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
_EXPAND = "body.storage,version,ancestors,metadata.labels,history"


def _normalize(link: str) -> str:
    """Confluence 'next' links may omit the /wiki context path."""
    return link if link.startswith("/wiki") else f"/wiki{link}"


@_retry
async def _get_json(url: str) -> Dict[str, Any]:
    response = await _get_client().get(url)
    response.raise_for_status()
    return response.json()


async def _paginate(url: str) -> AsyncIterator[Dict[str, Any]]:
    while url:
        data = await _get_json(url)
        for item in data.get("results", []):
            yield item
        next_link = data.get("_links", {}).get("next")
        url = _normalize(next_link) if next_link else ""


def iter_content(
    space_key: str, content_type: str = "page", page_size: int = 50
) -> AsyncIterator[Dict[str, Any]]:
    """Iterate every page (or blogpost) of a space, with body and metadata."""
    key = urllib.parse.quote(space_key)
    return _paginate(
        f"/wiki/rest/api/content?spaceKey={key}&type={content_type}"
        f"&status=current&expand={_EXPAND}&limit={page_size}"
    )


async def list_attachments(page_id: str) -> List[Dict[str, Any]]:
    """List all attachments of a page (title, mediaType, size, version, download link)."""
    url = (
        f"/wiki/rest/api/content/{urllib.parse.quote(page_id)}"
        "/child/attachment?expand=version&limit=100"
    )
    return [item async for item in _paginate(url)]


async def list_comments(page_id: str) -> List[Dict[str, Any]]:
    """List footer and inline comments of a page (storage format bodies)."""
    url = (
        f"/wiki/rest/api/content/{urllib.parse.quote(page_id)}"
        "/child/comment?expand=body.storage,version&limit=100"
    )
    return [item async for item in _paginate(url)]


@_retry
async def download(link: str) -> bytes:
    """Download a binary by Confluence link (relative) or absolute URL."""
    if link.startswith("http"):
        response = await _get_client().get(link, follow_redirects=True)
    else:
        response = await _get_client().get(_normalize(link), follow_redirects=True)
    response.raise_for_status()
    return response.content

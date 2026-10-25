"""Records describing a backed-up Confluence page and its attachments."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def _labels(item: Dict[str, Any]) -> List[str]:
    results = (item.get("metadata") or {}).get("labels", {}).get("results") or []
    return [label.get("name", "") for label in results if label.get("name")]


@dataclass
class AttachmentRecord:
    """A file stored next to the page: content-addressed under ``assets/``."""

    filename: str
    sha256: str
    media_type: str = ""
    size_bytes: int = 0
    version: int = 1
    path: str = ""


@dataclass
class PageRecord:
    """A Confluence page (or blogpost) plus the metadata the backup needs."""

    id: str
    title: str
    space_key: str
    version: int = 1
    content_type: str = "page"
    body_storage: str = ""
    url: str = ""
    parent_id: Optional[str] = None
    ancestors: List[Dict[str, str]] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    author: str = ""
    updated_at: str = ""

    @classmethod
    def from_api(
        cls, item: Dict[str, Any], space_key: str, base_url: str = ""
    ) -> "PageRecord":
        """Build a record from a ``rest/api/content`` item (missing fields tolerated)."""
        ancestors = [
            {"id": str(a.get("id", "")), "title": a.get("title", "")}
            for a in item.get("ancestors") or []
        ]
        version = item.get("version") or {}
        webui = (item.get("_links") or {}).get("webui") or ""
        return cls(
            id=str(item.get("id", "")),
            title=item.get("title", ""),
            space_key=space_key,
            version=int(version.get("number", 1) or 1),
            content_type=item.get("type") or "page",
            body_storage=((item.get("body") or {}).get("storage") or {}).get("value")
            or "",
            url=f"{base_url.rstrip('/')}{webui}" if webui else "",
            parent_id=str(ancestors[-1]["id"]) if ancestors else None,
            ancestors=ancestors,
            labels=_labels(item),
            author=((item.get("history") or {}).get("createdBy") or {}).get(
                "displayName", ""
            )
            or "",
            updated_at=version.get("when", "") or "",
        )

"""Image references inside Confluence storage format."""

import re
from dataclasses import dataclass
from typing import List

_IMAGE_RE = re.compile(r"<ac:image\b[^>]*?(?:/>|>(.*?)</ac:image>)", re.S)
_FILENAME_RE = re.compile(r'<ri:attachment\b[^>]*ri:filename="([^"]*)"', re.S)
_URL_RE = re.compile(r'<ri:url\b[^>]*ri:value="([^"]*)"', re.S)
_OWNER_RE = re.compile(r'<ri:page\b[^>]*ri:content-title="([^"]*)"', re.S)


@dataclass(frozen=True)
class ImageRef:
    """An image the page points at: an attachment or an external URL."""

    kind: str
    value: str
    page: str = ""


def find_image_refs(html: str) -> List[ImageRef]:
    """Every distinct image reference, in document order."""
    refs: List[ImageRef] = []
    for match in _IMAGE_RE.finditer(html or ""):
        inner = match.group(1) or ""
        filename = _FILENAME_RE.search(inner)
        url = _URL_RE.search(inner)
        if filename:
            owner = _OWNER_RE.search(inner)
            ref = ImageRef("attachment", filename.group(1), owner.group(1) if owner else "")
        elif url:
            ref = ImageRef("url", url.group(1))
        else:
            continue
        if ref not in refs:
            refs.append(ref)
    return refs

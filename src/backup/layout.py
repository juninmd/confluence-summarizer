"""On-disk layout of a space backup: paths, atomic writes, manifest, Markdown bits."""

import hashlib
import json
import os
import posixpath
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Union

from src.backup.models import PageRecord
from src.config import settings

MANIFEST = "manifest.json"
_ASSET_DIR = "assets"
_RAW_DIR = "_raw"
_MAX_SLUG = 60
_SPACE_RE = re.compile(r"^[A-Za-z0-9._~-]+$")
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")


def slugify(text: str) -> str:
    """Filesystem-friendly slug: no accents, no punctuation, bounded length."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    if not slug:
        return "untitled"
    return slug[:_MAX_SLUG].strip("-") or "untitled"


def _node(record: PageRecord) -> str:
    return f"{slugify(record.title)}-{record.id}"


def page_path(record: PageRecord) -> str:
    """Relative Markdown path mirroring the page hierarchy (blogposts go to blog/)."""
    if record.content_type == "blogpost":
        return posixpath.join("blog", _node(record), "index.md")
    parts = [f"{slugify(a.get('title', ''))}-{a.get('id', '')}" for a in record.ancestors]
    parts.append(_node(record))
    return posixpath.join(*parts, "index.md")


def relative_link(from_path: str, to_path: str) -> str:
    """``to_path`` (space-relative) as seen from the file ``from_path``."""
    return posixpath.relpath(to_path, posixpath.dirname(from_path) or ".")


def asset_path(data: bytes, filename: str) -> tuple[str, str]:
    """Content-addressed asset: returns (sha256, space-relative path)."""
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(filename or "").suffix.lower()
    return digest, posixpath.join(_ASSET_DIR, f"{digest}{suffix}")


def space_dir(space_key: str) -> Path:
    """Backup directory of a space, rejecting anything that could escape it."""
    if not space_key or not _SPACE_RE.match(space_key) or space_key in (".", ".."):
        raise ValueError(f"Invalid space key: {space_key!r}")
    return Path(settings.BACKUP_DIR) / space_key


def write_atomic(path: Union[str, Path], data: bytes) -> None:
    """Write through a temporary file so a crash never leaves a half-written page."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, target)


def load_manifest(directory: Union[str, Path]) -> Dict[str, Any]:
    """Read the space manifest (empty structure when there is no backup yet)."""
    path = Path(directory) / MANIFEST
    if not path.exists():
        return {"pages": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"pages": {}}
    data.setdefault("pages", {})
    return data


def save_manifest(directory: Union[str, Path], manifest: Dict[str, Any]) -> None:
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True)
    write_atomic(Path(directory) / MANIFEST, payload.encode("utf-8"))


def _front_value(value: Any) -> str:
    if isinstance(value, bool) or isinstance(value, int):
        return json.dumps(value)
    return json.dumps(value, ensure_ascii=False)


def front_matter(record: PageRecord) -> str:
    """YAML-ish front matter whose scalars are valid JSON (machine readable)."""
    head = {
        "id": record.id,
        "title": record.title,
        "space": record.space_key,
        "type": record.content_type,
        "version": record.version,
        "url": record.url,
        "labels": record.labels,
        "author": record.author,
        "updated_at": record.updated_at,
    }
    lines = [f"{key}: {_front_value(value)}" for key, value in head.items()]
    return "---\n" + "\n".join(lines) + "\n---\n"


def strip_front_matter(text: str) -> str:
    """Drop a leading ``---`` block; return the text untouched when absent."""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end == -1:
        return text
    rest = text[end + 4 :]
    return rest.lstrip("\n")


def local_links(markdown: str) -> List[str]:
    """Targets of relative links/images (absolute URLs, anchors and mailto ignored)."""
    return [
        target
        for target in _LINK_RE.findall(markdown)
        if not target.startswith(("http://", "https://", "mailto:", "#", "/"))
    ]


def rebase_links(markdown: str, from_dir: str, to_dir: str) -> str:
    """Rewrite relative links that were written while the file lived in ``from_dir``."""

    def replace(match: "re.Match[str]") -> str:
        whole, target = match.group(0), match.group(1)
        if target.startswith(("http://", "https://", "mailto:", "#", "/")):
            return whole
        resolved = posixpath.normpath(posixpath.join(from_dir, target))
        moved = posixpath.relpath(resolved, to_dir or ".")
        return whole.replace(f"({target})", f"({moved})")

    return _LINK_RE.sub(replace, markdown)


def raw_dir(directory: Union[str, Path], page_id: str) -> Path:
    return Path(directory) / _RAW_DIR / page_id


def iter_markdown(directory: Union[str, Path]) -> Iterable[Path]:
    return sorted(Path(directory).rglob("*.md"))

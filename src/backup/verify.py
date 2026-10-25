"""Verification of a space backup: files, links, assets and checksums."""

import hashlib
from pathlib import Path
from typing import Any, Dict, List

from src.backup import layout


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_space(space_key: str) -> List[str]:
    """Every inconsistency found in the backup of ``space_key`` (empty = healthy)."""
    try:
        space = layout.space_dir(space_key)
    except ValueError as exc:
        return [str(exc)]
    manifest: Dict[str, Any] = layout.load_manifest(space)
    if not manifest.get("pages"):
        return [f"No manifest found for space {space_key}"]

    problems: List[str] = []

    # Assets are content-addressed, so a rewrite/corruption is always visible.
    for rel, expected in (manifest.get("assets") or {}).items():
        asset = space / rel
        if not asset.exists():
            problems.append(f"Page ?: missing attachment {rel}")
        elif _sha256(asset) != expected:
            problems.append(f"Page ?: checksum mismatch for {rel}")

    for page_id in sorted(manifest["pages"]):
        entry = manifest["pages"][page_id]
        if entry.get("deleted"):
            continue
        rel = entry.get("path") or ""
        page_file = space / rel
        if not rel or not page_file.exists():
            problems.append(f"Page {page_id}: missing {rel}")
            continue
        markdown = page_file.read_text(encoding="utf-8", errors="replace")
        base = page_file.parent
        for target in layout.local_links(markdown):
            if not (base / target).exists():
                problems.append(f"Page {page_id}: broken link {target}")
        for attachment in entry.get("attachments") or []:
            asset = space / (attachment.get("path") or "")
            filename = attachment.get("filename") or asset.name
            if not asset.exists():
                problems.append(f"Page {page_id}: missing attachment {filename}")
            elif _sha256(asset) != attachment.get("sha256"):
                problems.append(f"Page {page_id}: checksum mismatch for {filename}")
        for image in entry.get("missing_images") or []:
            problems.append(f"Page {page_id}: image not backed up: {image}")

    for page_id, error in (manifest.get("errors") or {}).items():
        problems.append(f"Page {page_id} failed: {error}")
    backed_up = int(manifest.get("backed_up_pages") or 0)
    expected_pages = int(manifest.get("expected_pages") or 0)
    if backed_up < expected_pages:
        problems.append(f"Backed up {backed_up} of {expected_pages} pages")
    return problems

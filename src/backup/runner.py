"""Incremental backup of a Confluence space: raw storage, Markdown, assets and index."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.backup import layout
from src.backup.converter import Converter
from src.backup.models import AttachmentRecord, PageRecord
from src.backup.refs import ImageRef, find_image_refs
from src.config import settings
from src.db import pages as pages_db
from src.models.domain import ConfluencePage
from src.services import confluence_backup
from src.services import rag

logger = logging.getLogger(__name__)


def _digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _index_doc(record: PageRecord) -> ConfluencePage:
    return ConfluencePage(
        id=record.id,
        title=record.title,
        space_key=record.space_key,
        body=record.body_storage,
        version=record.version,
        url=record.url,
    )


class _SpaceBackup:
    def __init__(self, space_key: str) -> None:
        self.space_key = space_key
        self.dir = layout.space_dir(space_key)
        self.paths: Dict[str, str] = {}  # page id -> markdown path
        self.titles: Dict[str, str] = {}  # page title -> page id
        self.attachments: Dict[str, Dict[str, AttachmentRecord]] = {}
        self.assets: Dict[str, str] = {}

    # ── discovery ──────────────────────────────────────
    async def collect(self) -> List[Tuple[PageRecord, Dict[str, Any]]]:
        found: List[Tuple[PageRecord, Dict[str, Any]]] = []
        for kind in ("page", "blogpost"):
            async for item in confluence_backup.iter_content(self.space_key, kind):
                record = PageRecord.from_api(item, self.space_key, settings.CONFLUENCE_URL)
                found.append((record, item))
        for record, _ in found:
            self.paths[record.id] = layout.page_path(record)
            self.titles[record.title] = record.id
        return found

    # ── assets ─────────────────────────────────────────
    def _store(self, data: bytes, filename: str) -> Tuple[str, str]:
        sha, rel = layout.asset_path(data, filename)
        layout.write_atomic(self.dir / rel, data)
        self.assets[rel] = sha
        return sha, rel

    async def _attachments(
        self, record: PageRecord, previous: Optional[Dict[str, Any]]
    ) -> List[AttachmentRecord]:
        cached = {
            a.get("filename"): a
            for a in (previous or {}).get("attachments") or []
            if a.get("path")
        }
        records: List[AttachmentRecord] = []
        for item in await confluence_backup.list_attachments(record.id):
            filename = item.get("title") or ""
            version = int((item.get("version") or {}).get("number", 1) or 1)
            media_type = (item.get("extensions") or {}).get("mediaType", "") or ""
            known = cached.get(filename)
            if known and int(known.get("version", 0)) == version:
                asset = AttachmentRecord(
                    filename=filename,
                    sha256=known.get("sha256", ""),
                    media_type=known.get("media_type", media_type),
                    size_bytes=int(known.get("size_bytes", 0)),
                    version=version,
                    path=known.get("path", ""),
                )
                if asset.path:
                    self.assets[asset.path] = asset.sha256
                records.append(asset)
                continue
            link = (item.get("_links") or {}).get("download") or ""
            if not link:
                continue
            data = await confluence_backup.download(link)
            sha, rel = self._store(data, filename)
            records.append(
                AttachmentRecord(
                    filename=filename,
                    sha256=sha,
                    media_type=media_type,
                    size_bytes=len(data),
                    version=version,
                    path=rel,
                )
            )
            self.attachments.setdefault(record.id, {})[filename] = records[-1]
        for attachment in records:
            self.attachments.setdefault(record.id, {})[attachment.filename] = attachment
        return records

    def _resolvers(self, record: PageRecord):
        path = self.paths[record.id]

        def resolve_image(ref: ImageRef) -> Optional[str]:
            if ref.kind == "attachment":
                owner = self.titles.get(ref.page, record.id) if ref.page else record.id
                asset = self.attachments.get(owner, {}).get(ref.value)
                return layout.relative_link(path, asset.path) if asset else None
            rel = self._external.get(ref.value)
            return layout.relative_link(path, rel) if rel else None

        def resolve_link(title: str) -> Optional[str]:
            target = self.paths.get(self.titles.get(title, ""))
            return layout.relative_link(path, target) if target else None

        return resolve_image, resolve_link

    async def _external_images(self, record: PageRecord) -> None:
        """Fetch every external image (they carry no version, so always refreshed)."""
        self._external: Dict[str, str] = {}
        for ref in find_image_refs(record.body_storage):
            if ref.kind != "url" or ref.value in self._external:
                continue
            try:
                data = await confluence_backup.download(ref.value)
            except Exception as exc:  # missing external image is reported, not fatal
                logger.warning("External image %s not downloaded: %s", ref.value, exc)
                continue
            sha, rel = self._store(data, ref.value.split("?")[0])
            self._external[ref.value] = rel

    # ── one page ───────────────────────────────────────
    async def backup_page(
        self, record: PageRecord, raw: Dict[str, Any], previous: Optional[Dict[str, Any]], index: bool
    ) -> Dict[str, Any]:
        attachments = await self._attachments(record, previous)
        await self._external_images(record)

        resolve_image, resolve_link = self._resolvers(record)
        converter = Converter(resolve_image=resolve_image, resolve_link=resolve_link)
        body = converter.convert(record.body_storage)
        path = self.paths[record.id]
        markdown = f"{layout.front_matter(record)}\n# {record.title}\n\n{body}"

        raw_dir = layout.raw_dir(self.dir, record.id)
        layout.write_atomic(raw_dir / "body.storage.html", record.body_storage.encode())
        layout.write_atomic(
            raw_dir / "page.json", json.dumps(raw, ensure_ascii=False, indent=2).encode()
        )
        comments = await confluence_backup.list_comments(record.id)
        layout.write_atomic(
            raw_dir / "comments.json", json.dumps(comments, ensure_ascii=False, indent=2).encode()
        )

        entry = {
            "id": record.id,
            "title": record.title,
            "type": record.content_type,
            "version": record.version,
            "path": path,
            "deleted": False,
            "content_hash": _digest(record.body_storage),
            "missing_images": list(converter.missing_images),
            "attachments": [
                {
                    "filename": a.filename,
                    "sha256": a.sha256,
                    "media_type": a.media_type,
                    "size_bytes": a.size_bytes,
                    "version": a.version,
                    "path": a.path,
                }
                for a in attachments
            ],
        }

        changed = previous is None or (
            previous.get("version") != record.version
            or previous.get("content_hash") != entry["content_hash"]
        )
        if changed:
            layout.write_atomic(self.dir / path, markdown.encode("utf-8"))
            await pages_db.save_page(record, markdown, path, attachments)
            if index:
                await rag.ingest_page(_index_doc(record), text=body)
        return entry


async def backup_space(space_key: str, index: bool = True) -> Dict[str, Any]:
    """Back up (incrementally) a space; per-page failures never abort the run."""
    backup = _SpaceBackup(space_key)
    manifest = layout.load_manifest(backup.dir)
    pages: Dict[str, Any] = dict(manifest.get("pages") or {})
    errors: Dict[str, str] = {}

    found = await backup.collect()
    current = {record.id for record, _ in found}
    backed_up = 0
    for record, raw in found:
        try:
            pages[record.id] = await backup.backup_page(
                record, raw, pages.get(record.id), index
            )
            backed_up += 1
        except Exception as exc:  # a single page must not lose the whole run
            logger.warning("Backup of page %s failed: %s", record.id, exc)
            errors[record.id] = str(exc)

    deleted = [
        page_id
        for page_id, entry in pages.items()
        if page_id not in current and not entry.get("deleted")
    ]
    for page_id in deleted:
        pages[page_id]["deleted"] = True
    await pages_db.mark_deleted(deleted)

    manifest = {
        "space_key": space_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expected_pages": len(found),
        "backed_up_pages": backed_up,
        "errors": errors,
        "assets": backup.assets,
        "pages": pages,
    }
    layout.save_manifest(backup.dir, manifest)
    return manifest

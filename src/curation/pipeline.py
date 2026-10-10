"""Curation pipeline: cluster duplicates, resolve conflicts, unify, review, persist."""

import asyncio
import hashlib
import logging
import posixpath
import re
from typing import Any, Dict, List, Optional

from src.backup import layout
from src.config import settings
from src.curation import agents
from src.curation.cluster import find_clusters
from src.curation.export import export_doc
from src.curation.models import (
    Comparison,
    CuratedDoc,
    CurationStatus,
    SourcePage,
)
from src.db import curated, pages
from src.models.domain import RefinementStatus

logger = logging.getLogger(__name__)

_IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")


def cluster_id(space_key: str, page_ids: List[str]) -> str:
    """Stable id per set of sources, so re-runs update the same curated document."""
    return hashlib.sha1(
        f"{space_key}|{','.join(sorted(page_ids))}".encode()
    ).hexdigest()[:16]


def _title_of(markdown: str, fallback: str) -> str:
    match = re.search(r"^# (.+)$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else fallback


async def curate_group(space_key: str, group: List[SourcePage]) -> CuratedDoc:
    """Unify one group of pages (a single page is simply refined)."""
    ids = [p.id for p in group]
    cid = cluster_id(space_key, ids)
    try:
        comparison = await agents.compare(group) if len(group) > 1 else Comparison()
        text = await agents.unify(group, comparison)
        verdict = await agents.review(group, text)
    except Exception as exc:
        logger.exception(f"Curation of {ids} failed")
        return CuratedDoc(
            id=cid, space_key=space_key, source_ids=ids, title=group[0].title,
            markdown="", status=CurationStatus.FAILED, feedback=str(exc),
        )  # fmt: skip
    problems: List[str] = []
    if verdict.status != RefinementStatus.COMPLETED:
        problems.append(f"Reviewer: {verdict.feedback}")
    expected: set[str] = set()
    for page in group:
        expected.update(_IMAGE.findall(page.markdown))
    lost = sorted(expected - set(_IMAGE.findall(text)))
    if lost:  # deterministic guard: the LLM must never drop images
        problems.append(f"Images dropped: {lost}")
    needs_human = problems or any(c.needs_human for c in comparison.conflicts)
    return CuratedDoc(
        id=cid,
        space_key=space_key,
        source_ids=ids,
        title=_title_of(text, group[0].title),
        markdown=text,
        status=CurationStatus.NEEDS_REVIEW if needs_human else CurationStatus.APPROVED,
        conflicts=comparison.conflicts,
        feedback="; ".join(problems) or verdict.feedback,
    )


def _source(row: Any) -> SourcePage:
    text = layout.strip_front_matter(row["markdown"])
    return SourcePage(
        id=row["id"], title=row["title"], path=row["path"], version=row["version"],
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else "",
        markdown=layout.rebase_links(text, posixpath.dirname(row["path"]), ""),
    )  # fmt: skip


async def curate_space(
    space_key: str, threshold: Optional[float] = None
) -> Dict[str, Any]:
    """Curate every page of an already backed-up space; returns counts per status."""
    sources = {r["id"]: _source(r) for r in await pages.list_space_pages(space_key)}
    limit = settings.DUPLICATE_THRESHOLD if threshold is None else threshold
    groups = await find_clusters(space_key, sources, limit)
    sem = asyncio.Semaphore(settings.REFINEMENT_CONCURRENCY)

    async def one(ids: List[str]) -> str:
        cid = cluster_id(space_key, ids)
        if await curated.get_status(cid) == CurationStatus.HUMAN_APPROVED:
            return "skipped"
        async with sem:
            doc = await curate_group(space_key, [sources[i] for i in ids])
        await curated.save_curated(doc)
        if doc.markdown:
            export_doc(doc)
        return doc.status.value

    outcomes = await asyncio.gather(*(one(g) for g in groups))
    counts = {s: outcomes.count(s) for s in set(outcomes)}
    return {
        "space_key": space_key,
        "pages": len(sources),
        "documents": len(groups),
        "status": counts,
    }

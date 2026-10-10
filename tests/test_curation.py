import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.reviewer import ReviewResult
from src.config import settings
from src.curation import agents, cluster, export, pipeline
from src.curation.models import (
    Comparison,
    Conflict,
    CuratedDoc,
    CurationStatus,
    SourcePage,
)
from src.db import pool
from src.models.domain import RefinementStatus
from tests.fakes import FakePool


def src(pid: str, md: str = "# T\n\ntexto", title: str = "T") -> SourcePage:
    return SourcePage(
        id=pid, title=title, markdown=md, version=2, updated_at="2024-01-01"
    )


def test_group_pairs_builds_components():
    groups = cluster.group_pairs(
        ["1", "2", "3", "4", "5"], [("1", "2"), ("2", "3"), ("9", "1")]
    )
    assert groups == [["1", "2", "3"], ["4"], ["5"]]
    assert cluster.group_pairs([], []) == []


@pytest.mark.asyncio
async def test_find_clusters_queries_pgvector():
    fake = FakePool()
    fake.conn.rows = [{"a": "1", "b": "2"}]
    pool._pool = fake  # type: ignore[assignment]
    try:
        assert await cluster.find_clusters("DOC", ["1", "2", "3"], 0.9) == [
            ["1", "2"],
            ["3"],
        ]
    finally:
        pool._pool = None
    assert fake.conn.calls[0][2] == ("DOC", 0.9)
    assert "<=>" in fake.conn.calls[0][1]


def test_render_sources_truncates():
    text = agents.render_sources([src("1", "x" * 20000)])
    assert "id=1" in text and "version=2" in text and len(text) < 12300


@pytest.mark.asyncio
async def test_compare_parses_and_falls_back():
    payload = {
        "conflicts": [
            {
                "topic": "porta",
                "needs_human": True,
                "positions": [{"page_id": "1", "statement": "80"}],
            }
        ]
    }
    with patch(
        "src.curation.agents.generate_response",
        AsyncMock(return_value=f"```json\n{json.dumps(payload)}\n```"),
    ):
        result = await agents.compare([src("1"), src("2")])
    assert result.conflicts[0].topic == "porta" and result.conflicts[0].needs_human
    with patch(
        "src.curation.agents.generate_response", AsyncMock(return_value="not json")
    ):
        result = await agents.compare([src("1"), src("2")])
    assert result.conflicts[0].needs_human and "1" in result.conflicts[0].resolution


@pytest.mark.asyncio
async def test_unify_and_review():
    with patch(
        "src.curation.agents.generate_response", AsyncMock(return_value="  # Doc\n")
    ):
        assert await agents.unify([src("1")], Comparison()) == "# Doc\n"
    with patch("src.curation.agents.generate_response", AsyncMock(return_value=" ")):
        with pytest.raises(ValueError):
            await agents.unify([src("1")], Comparison())
    with patch(
        "src.curation.agents.generate_response",
        AsyncMock(return_value='{"status": "approved", "feedback": "ok"}'),
    ):
        verdict = await agents.review([src("1")], "# Doc")
    assert verdict.status == RefinementStatus.COMPLETED


def patch_agents(
    compare=None,
    unify="# Unificado\n\n![i](assets/a.png)\n",
    verdict=RefinementStatus.COMPLETED,
):
    return (
        patch(
            "src.curation.agents.compare",
            AsyncMock(return_value=compare or Comparison()),
        ),
        patch(
            "src.curation.agents.unify",
            (
                AsyncMock(side_effect=unify)
                if isinstance(unify, Exception)
                else AsyncMock(return_value=unify)
            ),
        ),
        patch(
            "src.curation.agents.review",
            AsyncMock(return_value=ReviewResult(status=verdict, feedback="fb")),
        ),
    )


async def run_group(group, **kw):
    a, b, c = patch_agents(**kw)
    with a as cmp, b, c:
        return await pipeline.curate_group("DOC", group), cmp


@pytest.mark.asyncio
async def test_curate_group_approved_and_single_page_skips_compare():
    doc, cmp = await run_group([src("1", "![i](assets/a.png)")])
    assert doc.status == CurationStatus.APPROVED and doc.title == "Unificado"
    assert doc.source_ids == ["1"] and doc.id == pipeline.cluster_id("DOC", ["1"])
    cmp.assert_not_awaited()
    doc, cmp = await run_group([src("1"), src("2")])
    cmp.assert_awaited_once()
    assert doc.id == pipeline.cluster_id("DOC", ["2", "1"])  # order independent


@pytest.mark.asyncio
async def test_curate_group_flags_for_human_review():
    doc, _ = await run_group([src("1")], verdict=RefinementStatus.FAILED)
    assert doc.status == CurationStatus.NEEDS_REVIEW and "Reviewer: fb" in doc.feedback

    doc, _ = await run_group([src("1", "![x](assets/lost.png)")])
    assert (
        doc.status == CurationStatus.NEEDS_REVIEW and "assets/lost.png" in doc.feedback
    )

    conflict = Comparison(conflicts=[Conflict(topic="t", needs_human=True)])
    doc, _ = await run_group([src("1"), src("2")], compare=conflict)
    assert doc.status == CurationStatus.NEEDS_REVIEW and len(doc.conflicts) == 1

    resolved = Comparison(conflicts=[Conflict(topic="t", resolution="usar v2")])
    doc, _ = await run_group([src("1"), src("2")], compare=resolved)
    assert doc.status == CurationStatus.APPROVED


@pytest.mark.asyncio
async def test_curate_group_failure_and_title_fallback():
    doc, _ = await run_group([src("1", title="Orig")], unify=ValueError("empty"))
    assert (
        doc.status == CurationStatus.FAILED
        and doc.feedback == "empty"
        and doc.markdown == ""
    )
    doc, _ = await run_group([src("1", title="Orig")], unify="sem titulo\n")
    assert doc.title == "Orig"


@pytest.mark.asyncio
async def test_curate_space_skips_human_approved_and_exports():
    rows = [
        {
            "id": "1",
            "title": "A",
            "markdown": "---\nid: 1\n---\n\n# A\n\n![i](../assets/a.png)",
            "path": "x-1/index.md",
            "version": 1,
            "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        },
        {
            "id": "2",
            "title": "B",
            "markdown": "# B",
            "path": "b-2/index.md",
            "version": 1,
            "updated_at": None,
        },
        {
            "id": "3",
            "title": "C",
            "markdown": "# C",
            "path": "c-3/index.md",
            "version": 1,
            "updated_at": None,
        },
    ]
    locked = pipeline.cluster_id("DOC", ["3"])

    async def status(cid):
        return CurationStatus.HUMAN_APPROVED if cid == locked else None

    save, exp = AsyncMock(), MagicMock()
    seen = []

    async def fake_group(space, group):
        seen.append([p.markdown for p in group])
        return CuratedDoc(
            id=pipeline.cluster_id(space, [p.id for p in group]),
            space_key=space,
            title="U",
            markdown="# U" if group[0].id == "1" else "",
            status=CurationStatus.APPROVED,
        )

    with (
        patch(
            "src.curation.pipeline.pages.list_space_pages", AsyncMock(return_value=rows)
        ),
        patch(
            "src.curation.pipeline.find_clusters",
            AsyncMock(return_value=[["1", "2"], ["3"]]),
        ),
        patch("src.curation.pipeline.curated.get_status", status),
        patch("src.curation.pipeline.curated.save_curated", save),
        patch("src.curation.pipeline.export_doc", exp),
        patch("src.curation.pipeline.curate_group", fake_group),
    ):
        summary = await pipeline.curate_space("DOC", threshold=0.5)
    assert (
        summary["status"] == {"approved": 1, "skipped": 1} and summary["documents"] == 2
    )
    # links were rebased to the space root and front matter stripped before the LLM sees them
    assert seen == [["# A\n\n![i](assets/a.png)", "# B"]]
    save.assert_awaited_once()
    exp.assert_called_once()


def test_export_rebases_links(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    doc = CuratedDoc(
        id="abcdef123456",
        space_key="DOC",
        title="Meu Doc",
        status=CurationStatus.APPROVED,
        markdown="# Meu Doc\n\n![i](assets/a.png)",
        source_ids=["1", "2"],
    )
    path = export.export_doc(doc)
    assert path == tmp_path / "DOC/curated/meu-doc-abcdef12.md"
    text = path.read_text()
    assert (
        "![i](../assets/a.png)" in text
        and 'status: "approved"' in text
        and '"sources": ' not in text
    )
    assert 'sources: ["1", "2"]' in text

"""End-to-end backup against a simulated Confluence, with DB/embeddings mocked."""

import copy
from unittest.mock import AsyncMock, patch

import pytest

from src.backup import layout, runner
from src.backup.verify import verify_space
from src.config import settings

PNG_A = b"\x89PNG-a"
PNG_EXT = b"\x89PNG-external"
LOGO = b"\x89PNG-logo"

IMG = '<ac:image ac:alt="A"><ri:attachment ri:filename="a.png"/></ac:image>'
OWNED = (
    '<ac:image><ri:attachment ri:filename="a.png"><ri:page ri:content-title="Raiz"/>'
    "</ri:attachment></ac:image>"
)
EXT = '<ac:image><ri:url ri:value="https://cdn.io/ext.png?x=1"/></ac:image>'
LINK = '<ac:link><ri:page ri:content-title="Filho"/><ac:link-body>filho</ac:link-body></ac:link>'

CONTENT = {
    "page": [
        {
            "id": "1",
            "title": "Raiz",
            "version": {"number": 1},
            "body": {"storage": {"value": f"<p>{IMG}{EXT}{LINK}</p>"}},
        },
        {
            "id": "2",
            "title": "Filho",
            "ancestors": [{"id": "1", "title": "Raiz"}],
            "version": {"number": 1},
            "body": {"storage": {"value": f"<p>{OWNED}</p>"}},
        },
    ],
    "blogpost": [
        {
            "id": "3",
            "title": "Post",
            "type": "blogpost",
            "version": {"number": 1},
            "body": {"storage": {"value": "<p>blog</p>"}},
        }
    ],
}
ATTACHMENTS = {
    "1": [
        {
            "title": "a.png",
            "version": {"number": 1},
            "extensions": {"mediaType": "image/png"},
            "_links": {"download": "/download/a.png"},
        },
        {
            "title": "logo.png",
            "version": {"number": 1},
            "_links": {"download": "/download/logo.png"},
        },
    ]
}
FILES = {
    "/download/a.png": PNG_A,
    "/download/logo.png": LOGO,
    "https://cdn.io/ext.png?x=1": PNG_EXT,
}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    state = {"content": copy.deepcopy(CONTENT), "fail_attachments": set()}

    async def iter_content(space, kind="page", page_size=50):
        for item in state["content"][kind]:
            yield {**item, "type": item.get("type", "page")}

    async def list_attachments(page_id):
        if page_id in state["fail_attachments"]:
            raise RuntimeError("boom")
        return ATTACHMENTS.get(page_id, [])

    download = AsyncMock(side_effect=lambda link: FILES[link])
    save, deleted, ingest = AsyncMock(), AsyncMock(), AsyncMock()
    with (
        patch("src.services.confluence_backup.iter_content", iter_content),
        patch("src.services.confluence_backup.list_attachments", list_attachments),
        patch(
            "src.services.confluence_backup.list_comments",
            AsyncMock(return_value=[{"id": "c"}]),
        ),
        patch("src.services.confluence_backup.download", download),
        patch("src.db.pages.save_page", save),
        patch("src.db.pages.mark_deleted", deleted),
        patch("src.services.rag.ingest_page", ingest),
    ):
        yield state, tmp_path / "DOC", download, save, deleted, ingest


@pytest.mark.asyncio
async def test_full_backup_writes_markdown_images_and_raw(world):
    _, space, download, save, _, ingest = world
    manifest = await runner.backup_space("DOC")

    assert (
        manifest["errors"] == {}
        and manifest["backed_up_pages"] == manifest["expected_pages"] == 3
    )
    root = (space / "raiz-1/index.md").read_text()
    assert root.startswith('---\nid: "1"') and "# Raiz" in root
    assert "![A](../assets/" in root  # attachment of the page itself
    assert "[filho](filho-2/index.md)" in root  # internal link resolved to a file
    child = (space / "raiz-1/filho-2/index.md").read_text()
    assert (
        "![image](../../assets/" not in child and "](../../assets/" in child
    )  # owner page image
    assert "blog" in (space / "blog/post-3/index.md").read_text()
    assert (
        list((space / "assets").glob("*.png")).__len__() == 3
    )  # a.png, logo.png, external
    assert (space / "_raw/1/body.storage.html").exists()
    assert (space / "_raw/1/page.json").exists() and (
        space / "_raw/1/comments.json"
    ).exists()
    assert (
        download.await_count == 3 and save.await_count == 3 and ingest.await_count == 3
    )
    assert verify_space("DOC") == []


@pytest.mark.asyncio
async def test_second_run_is_incremental_and_idempotent(world):
    state, space, download, save, _, ingest = world
    await runner.backup_space("DOC")
    snapshot = {p: p.read_bytes() for p in space.rglob("*.md")}
    download.reset_mock()
    save.reset_mock()
    ingest.reset_mock()  # noqa: E702

    await runner.backup_space("DOC", index=False)
    assert (
        download.await_count == 1
    )  # external image has no version info: refetched only
    assert save.await_count == 0 and ingest.await_count == 0
    assert {p: p.read_bytes() for p in space.rglob("*.md")} == snapshot

    state["content"]["page"][1]["version"] = {"number": 2}
    await runner.backup_space("DOC", index=False)
    assert save.await_count == 1 and ingest.await_count == 0


@pytest.mark.asyncio
async def test_deleted_pages_are_kept_and_flagged(world):
    state, space, _, _, deleted, _ = world
    await runner.backup_space("DOC")
    state["content"]["blogpost"] = []
    manifest = await runner.backup_space("DOC")
    assert manifest["pages"]["3"]["deleted"] is True
    assert (space / "blog/post-3/index.md").exists()  # never pruned
    deleted.assert_awaited_with(["3"])
    await runner.backup_space("DOC")  # already flagged: not reported again
    deleted.assert_awaited_with([])


@pytest.mark.asyncio
async def test_page_failure_is_isolated_and_reported(world):
    state, _, _, save, _, _ = world
    state["fail_attachments"].add("1")
    manifest = await runner.backup_space("DOC")
    assert list(manifest["errors"]) == ["1"] and manifest["backed_up_pages"] == 2
    assert "1" not in manifest["pages"]
    problems = verify_space("DOC")
    assert any("Page 1 failed" in p for p in problems)
    assert any("Backed up 2 of 3" in p for p in problems)

    state["fail_attachments"].clear()
    save.side_effect = RuntimeError("db down")  # only page 1 changed since the last run
    manifest = await runner.backup_space("DOC")
    assert "db down" in manifest["errors"]["1"]


@pytest.mark.asyncio
async def test_failed_page_keeps_previous_entry(world):
    state, _, _, _, _, _ = world
    await runner.backup_space("DOC")
    state["fail_attachments"].add("1")
    manifest = await runner.backup_space("DOC")
    assert (
        manifest["pages"]["1"]["deleted"] is False
    )  # old entry survives a transient error


@pytest.mark.asyncio
async def test_external_image_failure_becomes_missing_image(world):
    _, space, download, _, _, _ = world

    def fetch(link):
        if link.startswith("https://cdn"):
            raise RuntimeError("404")
        return FILES[link]

    download.side_effect = fetch
    manifest = await runner.backup_space("DOC")
    assert manifest["pages"]["1"]["missing_images"] == ["https://cdn.io/ext.png?x=1"]
    assert any("image not backed up" in p for p in verify_space("DOC"))


@pytest.mark.asyncio
async def test_verify_detects_corruption(world):
    _, space, _, _, _, _ = world
    await runner.backup_space("DOC")
    assert verify_space("NOPE") == ["No manifest found for space NOPE"]

    asset = next((space / "assets").glob("*.png"))
    asset.write_bytes(b"tampered")
    assert any("checksum mismatch" in p for p in verify_space("DOC"))
    for png in (space / "assets").glob("*.png"):
        png.unlink()
    problems = verify_space("DOC")
    assert any("missing attachment" in p for p in problems)
    assert any("broken link" in p for p in problems)
    (space / "blog/post-3/index.md").unlink()
    assert any("Page 3: missing" in p for p in verify_space("DOC"))
    assert layout.load_manifest(space)["pages"]

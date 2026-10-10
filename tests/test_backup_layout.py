import json

import pytest

from src.backup import layout
from src.backup.models import PageRecord
from src.config import settings


def make_page(**kw) -> PageRecord:
    base = dict(id="10", title="Guia de Início", space_key="DOC", version=3)
    return PageRecord(**{**base, **kw})


def test_slugify():
    assert layout.slugify("Guia de Início!") == "guia-de-inicio"
    assert layout.slugify("???") == "untitled"
    assert len(layout.slugify("a" * 200)) == 60


def test_page_path_mirrors_hierarchy():
    page = make_page(
        ancestors=[{"id": "1", "title": "Raiz"}, {"id": "2", "title": "Filho"}]
    )
    assert layout.page_path(page) == "raiz-1/filho-2/guia-de-inicio-10/index.md"
    assert (
        layout.page_path(make_page(content_type="blogpost"))
        == "blog/guia-de-inicio-10/index.md"
    )


def test_relative_link_and_asset_path():
    assert layout.relative_link("a/b/index.md", "assets/x.png") == "../../assets/x.png"
    sha, rel = layout.asset_path(b"data", "Foto.PNG")
    assert rel == f"assets/{sha}.png" and len(sha) == 64


def test_space_dir_rejects_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    assert layout.space_dir("DOC") == tmp_path / "DOC"
    assert layout.space_dir("~user") == tmp_path / "~user"
    for bad in ("../x", "a/b", "", "a b"):
        with pytest.raises(ValueError):
            layout.space_dir(bad)


def test_write_atomic_and_manifest_roundtrip(tmp_path):
    layout.write_atomic(tmp_path / "x" / "f.bin", b"1")
    assert (tmp_path / "x" / "f.bin").read_bytes() == b"1"
    assert not list(tmp_path.rglob("*.tmp"))
    assert layout.load_manifest(tmp_path) == {"pages": {}}
    layout.save_manifest(tmp_path, {"pages": {"1": {"título": "ç"}}})
    assert layout.load_manifest(tmp_path)["pages"]["1"]["título"] == "ç"


def test_front_matter_is_valid_json_scalars():
    text = layout.front_matter(make_page(labels=["a"], author='Ana "A"'))
    lines = text.strip().split("\n")
    assert lines[0] == lines[-1] == "---"
    assert (
        'author: "Ana \\"A\\""' in text
        and json.loads(lines[2].split(": ", 1)[1]) == "Guia de Início"
    )
    assert layout.strip_front_matter(text + "# T\n") == "# T\n"
    assert layout.strip_front_matter("sem front") == "sem front"


def test_local_links_and_rebase():
    md = "![i](../assets/a.png) [p](x/index.md) [u](https://e.io) [m](mailto:a@b) [h](#top) [r](/abs)"
    assert layout.local_links(md) == ["../assets/a.png", "x/index.md"]
    moved = layout.rebase_links(md, "a/b", "")
    assert "![i](a/assets/a.png)" in moved and "[p](a/b/x/index.md)" in moved
    assert "(https://e.io)" in moved and "(#top)" in moved
    back = layout.rebase_links("![i](assets/a.png)", "", "curated")
    assert back == "![i](../assets/a.png)"

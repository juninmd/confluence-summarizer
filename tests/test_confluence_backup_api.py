from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backup.models import PageRecord
from src.services import confluence_backup as cb


def response(payload=None, content=b""):
    r = MagicMock()
    r.json.return_value = payload
    r.content = content
    r.raise_for_status.return_value = None
    return r


@pytest.fixture
def client():
    c = AsyncMock()
    with patch("src.services.confluence_backup._get_client", return_value=c):
        yield c


@pytest.mark.asyncio
async def test_iter_content_follows_next_links(client):
    client.get.side_effect = [
        response(
            {"results": [{"id": 1}], "_links": {"next": "/rest/api/content?start=1"}}
        ),
        response({"results": [{"id": 2}], "_links": {}}),
    ]
    items = [i async for i in cb.iter_content("DOC", "page", page_size=1)]
    assert [i["id"] for i in items] == [1, 2]
    first, second = (c.args[0] for c in client.get.call_args_list)
    assert "spaceKey=DOC" in first and "body.storage" in first
    assert second == "/wiki/rest/api/content?start=1"


@pytest.mark.asyncio
async def test_attachments_and_comments(client):
    client.get.return_value = response({"results": [{"title": "a.png"}], "_links": {}})
    assert await cb.list_attachments("5") == [{"title": "a.png"}]
    assert await cb.list_comments("5") == [{"title": "a.png"}]
    urls = [c.args[0] for c in client.get.call_args_list]
    assert "/child/attachment" in urls[0] and "/child/comment" in urls[1]


@pytest.mark.asyncio
async def test_download_relative_and_absolute(client):
    client.get.return_value = response(content=b"bin")
    assert await cb.download("/download/attachments/1/a.png") == b"bin"
    assert await cb.download("https://cdn.io/x.png") == b"bin"
    urls = [c.args[0] for c in client.get.call_args_list]
    assert urls == ["/wiki/download/attachments/1/a.png", "https://cdn.io/x.png"]
    assert all(c.kwargs["follow_redirects"] for c in client.get.call_args_list)


def test_page_record_from_api():
    item = {
        "id": 7,
        "title": "T",
        "type": "page",
        "ancestors": [{"id": 1, "title": "R"}, {"id": 2, "title": "P"}],
        "metadata": {"labels": {"results": [{"name": "x"}]}},
        "version": {"number": 4, "when": "2024-01-01T00:00:00.000Z"},
        "history": {"createdBy": {"displayName": "Ana"}},
        "_links": {"webui": "/spaces/D/pages/7"},
        "body": {"storage": {"value": "<p>x</p>"}},
    }
    rec = PageRecord.from_api(item, "D", "https://c.io/wiki")
    assert (rec.id, rec.parent_id, rec.labels, rec.version) == ("7", "2", ["x"], 4)
    assert rec.author == "Ana" and rec.url == "https://c.io/wiki/spaces/D/pages/7"
    bare = PageRecord.from_api({"id": 1, "title": "T"}, "D", "https://c.io")
    assert bare.parent_id is None and bare.url == "" and bare.body_storage == ""

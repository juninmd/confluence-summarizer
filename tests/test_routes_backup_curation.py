from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src import routes_backup
from src.backup import layout
from src.config import settings
from src.curation.models import CuratedDoc, CurationStatus
from src.main import app

HEADERS = {"X-API-Key": "dummy-api-key"}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "APP_API_KEY", "dummy-api-key")
    routes_backup._running.clear()
    app.state.limiter.reset()
    return TestClient(app)


def test_auth_required(client):
    assert client.post("/backup/space/DOC").status_code == 401
    assert client.get("/curate/space/DOC").status_code == 401


def test_start_backup_runs_in_background(client):
    manifest = {"backed_up_pages": 2}
    with patch(
        "src.routes_backup.backup_space", AsyncMock(return_value=manifest)
    ) as run:
        resp = client.post("/backup/space/DOC?index=false", headers=HEADERS)
    assert resp.status_code == 202
    run.assert_awaited_once_with("DOC", index=False)
    assert "DOC" not in routes_backup._running


def test_backup_rejects_bad_key_and_concurrent_run(client):
    assert client.post("/backup/space/..%2Fx", headers=HEADERS).status_code in (
        400,
        404,
    )
    assert client.get("/backup/space/a%20b", headers=HEADERS).status_code == 400
    routes_backup._running.add("DOC")
    assert client.post("/backup/space/DOC", headers=HEADERS).status_code == 409


def test_backup_failure_is_contained(client):
    with patch(
        "src.routes_backup.backup_space", AsyncMock(side_effect=RuntimeError("x"))
    ):
        assert client.post("/backup/space/DOC", headers=HEADERS).status_code == 202
    assert "DOC" not in routes_backup._running


def test_backup_status_and_verify(client, tmp_path):
    assert client.get("/backup/space/DOC", headers=HEADERS).status_code == 404
    layout.save_manifest(
        tmp_path / "DOC",
        {
            "expected_pages": 2,
            "backed_up_pages": 2,
            "errors": {},
            "pages": {
                "1": {"deleted": False, "path": "x/index.md"},
                "2": {"deleted": True, "path": "y"},
            },
        },
    )
    body = client.get("/backup/space/DOC", headers=HEADERS).json()
    assert (
        body["total_pages"] == 2
        and body["deleted_pages"] == 1
        and body["running"] is False
    )
    verify = client.get("/backup/space/DOC/verify", headers=HEADERS).json()
    assert verify["ok"] is False and "missing x/index.md" in verify["problems"][0]


def test_curation_endpoints(client, tmp_path):
    with patch("src.routes_curation.curate_space", AsyncMock(return_value={})) as run:
        resp = client.post("/curate/space/DOC?threshold=0.9", headers=HEADERS)
    assert resp.status_code == 202
    run.assert_awaited_once_with("DOC", 0.9)
    with patch("src.routes_curation.curate_space", AsyncMock(side_effect=RuntimeError)):
        assert client.post("/curate/space/DOC", headers=HEADERS).status_code == 202

    with patch(
        "src.routes_curation.curated.list_curated",
        AsyncMock(return_value=[{"id": "c1", "status": "approved"}]),
    ) as lst:
        body = client.get(
            "/curate/space/DOC?doc_status=approved", headers=HEADERS
        ).json()
    assert body["documents"] == [{"id": "c1", "status": "approved"}]
    lst.assert_awaited_once_with("DOC", "approved")

    doc = CuratedDoc(
        id="c1",
        space_key="DOC",
        title="T",
        markdown="# T",
        status=CurationStatus.NEEDS_REVIEW,
    )
    with patch("src.routes_curation.curated.get_curated", AsyncMock(return_value=doc)):
        assert client.get("/curate/doc/c1", headers=HEADERS).json()["title"] == "T"
    with patch("src.routes_curation.curated.get_curated", AsyncMock(return_value=None)):
        assert client.get("/curate/doc/zz", headers=HEADERS).status_code == 404


def test_approve_doc(client, tmp_path):
    doc = CuratedDoc(
        id="c1",
        space_key="DOC",
        title="T",
        markdown="# T",
        status=CurationStatus.HUMAN_APPROVED,
    )
    with (
        patch(
            "src.routes_curation.curated.set_status", AsyncMock(return_value=True)
        ) as setter,
        patch("src.routes_curation.curated.get_curated", AsyncMock(return_value=doc)),
        patch("src.routes_curation.export_doc") as exp,
    ):
        assert client.post("/curate/doc/c1/approve", headers=HEADERS).status_code == 200
    setter.assert_awaited_once_with("c1", CurationStatus.HUMAN_APPROVED)
    exp.assert_called_once_with(doc)
    with patch("src.routes_curation.curated.set_status", AsyncMock(return_value=False)):
        assert client.post("/curate/doc/zz/approve", headers=HEADERS).status_code == 404

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src import config
from src.database import init_db, save_job_sync
from src.main import app
from src.models.domain import ConfluencePage, RefinementJob, RefinementStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    config.settings.DB_PATH = str(tmp_path / "publish.db")
    init_db()


@pytest.mark.parametrize("current_version", [1, 7])
def test_publish_sends_current_version_plus_one(current_version):
    """Confluence returns 409 unless the update carries current version + 1."""
    job = RefinementJob(
        id=f"pub-{current_version}",
        page_id="page1",
        status=RefinementStatus.COMPLETED,
        refined_text="New text",
    )
    save_job_sync(job)
    page = ConfluencePage(
        id="page1", title="T", space_key="S", body="Old", version=current_version
    )

    with (
        patch("src.services.confluence.get_page", new_callable=AsyncMock) as get,
        patch("src.services.confluence.update_page", new_callable=AsyncMock) as upd,
    ):
        get.return_value = page
        response = client.post(
            f"/publish/{job.id}", headers={"X-API-Key": "dummy-api-key"}
        )

    assert response.status_code == 200
    assert upd.call_args.kwargs["version_number"] == current_version + 1


def test_publish_failure_does_not_echo_upstream_error():
    """httpx errors carry the Confluence URL and body; the API must not return them."""
    job = RefinementJob(
        id="pub-leak",
        page_id="page1",
        status=RefinementStatus.COMPLETED,
        refined_text="New text",
    )
    save_job_sync(job)
    leak = "Server error '500' for url 'https://intranet.example/wiki/api/v2/pages/1'"

    with patch("src.services.confluence.get_page", new_callable=AsyncMock) as get:
        get.side_effect = Exception(leak)
        response = client.post(
            f"/publish/{job.id}", headers={"X-API-Key": "dummy-api-key"}
        )

    assert response.status_code == 500
    assert "intranet.example" not in response.text
    assert response.json()["detail"].startswith("Publishing failed")

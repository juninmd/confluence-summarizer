import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from confluence_summarizer.main import app
from confluence_summarizer.models import RefinementResult, RefinementStatus, ConfluencePage


@pytest.fixture
def client():
    # Patch init_db and init_rag to avoid real DB creation during startup
    with patch("confluence_summarizer.database.init_db", new_callable=AsyncMock), \
         patch("confluence_summarizer.services.rag.init_rag", new_callable=AsyncMock):
        with TestClient(app) as c:
            yield c


@pytest.fixture
def mock_confluence_get_page():
    with patch("confluence_summarizer.services.confluence.get_page", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_refine_page():
    with patch("confluence_summarizer.main.refine_page", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_db():
    # We patch the functions in the database module that main imports
    with patch("confluence_summarizer.database.save_job", new_callable=AsyncMock) as mock_save, \
         patch("confluence_summarizer.database.get_job", new_callable=AsyncMock) as mock_get, \
         patch("confluence_summarizer.database.init_db", new_callable=AsyncMock) as mock_init:
        yield mock_save, mock_get, mock_init


def test_start_refinement(client, mock_confluence_get_page, mock_refine_page, mock_db):
    mock_save, mock_get, _ = mock_db

    # Setup mocks
    mock_confluence_get_page.return_value = ConfluencePage(
        id="123", title="Test Page", body="Content", space_key="TEST", version=1, url="http://example.com"
    )
    mock_refine_page.return_value = RefinementResult(
        page_id="123", original_content="Content", status=RefinementStatus.COMPLETED
    )

    # Action
    response = client.post("/refine/123")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["page_id"] == "123"
    assert data["message"] == "Refinement job started"

    # Verify DB save was called (initially with PROCESSING)
    assert mock_save.called


def test_get_status_not_found(client, mock_db):
    mock_save, mock_get, _ = mock_db
    mock_get.return_value = None

    response = client.get("/status/nonexistent")
    assert response.status_code == 404


def test_get_status_found(client, mock_db):
    mock_save, mock_get, _ = mock_db
    mock_get.return_value = RefinementResult(
        page_id="456", original_content="Org", status=RefinementStatus.PROCESSING
    )

    response = client.get("/status/456")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"


@pytest.fixture
def mock_confluence_update_page():
    with patch("confluence_summarizer.services.confluence.update_page", new_callable=AsyncMock) as mock:
        yield mock


def test_publish_page_success(client, mock_confluence_get_page, mock_confluence_update_page, mock_db):
    mock_save, mock_get, _ = mock_db

    mock_get.return_value = RefinementResult(
        page_id="789",
        original_content="Org",
        status=RefinementStatus.COMPLETED,
        rewritten_content="New Content"
    )

    mock_confluence_get_page.return_value = ConfluencePage(
        id="789", title="Page", body="Org", space_key="S", version=1, url="url"
    )
    mock_confluence_update_page.return_value = ConfluencePage(
        id="789", title="Page", body="New Content", space_key="S", version=2, url="url"
    )

    response = client.post("/publish/789")

    assert response.status_code == 200
    assert response.json()["message"] == "Page published successfully"
    mock_confluence_update_page.assert_called_once()


def test_publish_page_not_found(client, mock_db):
    mock_save, mock_get, _ = mock_db
    mock_get.return_value = None
    response = client.post("/publish/999")
    assert response.status_code == 404


def test_publish_page_not_completed(client, mock_db):
    mock_save, mock_get, _ = mock_db
    mock_get.return_value = RefinementResult(
        page_id="888", original_content="Org", status=RefinementStatus.PROCESSING
    )
    response = client.post("/publish/888")
    assert response.status_code == 400


def test_publish_page_no_content(client, mock_db):
    mock_save, mock_get, _ = mock_db
    mock_get.return_value = RefinementResult(
        page_id="789",
        original_content="Org",
        status=RefinementStatus.COMPLETED,
        rewritten_content=""  # Empty
    )
    response = client.post("/publish/789")
    assert response.status_code == 400
    assert "No rewritten content available" in response.json()["detail"]


def test_publish_page_update_failure(client, mock_confluence_get_page, mock_confluence_update_page, mock_db):
    mock_save, mock_get, _ = mock_db
    mock_get.return_value = RefinementResult(
        page_id="789",
        original_content="Org",
        status=RefinementStatus.COMPLETED,
        rewritten_content="New Content"
    )
    mock_confluence_get_page.return_value = ConfluencePage(
        id="789", title="Page", body="Org", space_key="S", version=1, url="url"
    )
    mock_confluence_update_page.side_effect = Exception("Confluence Down")

    response = client.post("/publish/789")
    assert response.status_code == 500
    assert "Failed to publish" in response.json()["detail"]


def test_ingest_space(client):
    with patch("confluence_summarizer.main.process_space_ingestion", new_callable=AsyncMock):
        response = client.post("/ingest/space/TEST")
        assert response.status_code == 200
        assert "Ingestion started" in response.json()["message"]


def test_start_space_refinement(client):
    with patch("confluence_summarizer.main.process_space_refinement", new_callable=AsyncMock) as mock_task:
        response = client.post("/refine/space/TEST_SPACE")
        assert response.status_code == 200
        assert "Refinement started for space TEST_SPACE" in response.json()["message"]
        mock_task.assert_awaited_with("TEST_SPACE")

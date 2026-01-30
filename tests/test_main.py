import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from confluence_refiner.main import app
from confluence_refiner.models import RefinementResult, RefinementStatus, ConfluencePage

client = TestClient(app)


@pytest.fixture
def mock_confluence_get_page():
    with patch("confluence_refiner.services.confluence.get_page", new_callable=AsyncMock) as mock:
        yield mock


@pytest.fixture
def mock_refine_page():
    with patch("confluence_refiner.main.refine_page", new_callable=AsyncMock) as mock:
        yield mock


def test_start_refinement(mock_confluence_get_page, mock_refine_page):
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


def test_get_status_not_found():
    response = client.get("/status/nonexistent")
    assert response.status_code == 404


def test_get_status_found(mock_confluence_get_page, mock_refine_page):
    # We need to simulate the background task logic or just manually insert into the jobs dict
    # Since we can't easily wait for background tasks in sync test client without overhead,
    # we'll inject into the jobs dict directly for this test.
    from confluence_refiner.main import jobs

    jobs["456"] = RefinementResult(
        page_id="456", original_content="Org", status=RefinementStatus.PROCESSING
    )

    response = client.get("/status/456")
    assert response.status_code == 200
    assert response.json()["status"] == "processing"

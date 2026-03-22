import pytest


from unittest.mock import AsyncMock
from src.confluence_summarizer.main import _perform_refinement
from src.confluence_summarizer.database import update_job, get_job, init_db
from src.confluence_summarizer.services.confluence import get_pages_in_space, init_client, close_client
from src.confluence_summarizer.config import settings

@pytest.fixture(autouse=True)
def setup_teardown_db():
    import os
    if os.path.exists("jobs_test.db"):
        os.remove("jobs_test.db")
    settings.db_path = "jobs_test.db"
    init_db()

@pytest.mark.asyncio
async def test_refinement_error_handling(mocker):
    """Testa captura de exceção e set do job status FAILED durante refinamento."""
    # Ensure it mocks correctly as an async exception
    mock_get = AsyncMock(side_effect=Exception("API Down"))
    mocker.patch("src.confluence_summarizer.main.get_page_by_id", mock_get)
    job_id = "test-fail-123"

    # Needs to be created before updated
    from src.confluence_summarizer.database import create_job
    await create_job(job_id, "page_err_id")

    await _perform_refinement(job_id, "page_err_id")

    job = await get_job(job_id)
    assert job.status == "FAILED"
    assert "API Down" in job.error

@pytest.mark.asyncio
async def test_confluence_pagination(mocker):
    """Verifica lógica de limite e chunks para Confluence GET Pages in Space usando links iterativos."""
    # Primeiro mocka a resposta com próxima página
    mock_resp_1 = mocker.Mock()
    mock_resp_1.raise_for_status = mocker.Mock()
    mock_resp_1.json.return_value = {
        "results": [{"id": "1"}, {"id": "2"}],
        "_links": {"next": "/wiki/api/v2/spaces/TEST/pages?cursor=abcd"}
    }

    # Segunda reposta sem próxima página
    mock_resp_2 = mocker.Mock()
    mock_resp_2.raise_for_status = mocker.Mock()
    mock_resp_2.json.return_value = {
        "results": [{"id": "3"}],
        "_links": {}
    }

    mock_client = AsyncMock()
    mock_client.get.side_effect = [mock_resp_1, mock_resp_2]

    mocker.patch("src.confluence_summarizer.services.confluence._client", mock_client)
    mocker.patch("src.confluence_summarizer.services.confluence._get_http_client", return_value=mock_client)

    pages = await get_pages_in_space("TEST_SPACE", limit=2)
    assert len(pages) == 3
    assert pages[2]["id"] == "3"
    assert mock_client.get.call_count == 2

@pytest.mark.asyncio
async def test_client_idempotency():
    """Garante que start e stop client do lifespan não crashem e reaproveitem a pool global."""
    init_client()
    import src.confluence_summarizer.services.confluence as conf
    assert conf._client is not None
    await close_client()
    assert conf._client is None
    # Chamando novamente para testar idempotência
    await close_client()

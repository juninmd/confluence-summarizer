
import pytest
from src.confluence_summarizer.config import settings

@pytest.fixture(autouse=True)
def dummy_env_vars():
    """Ensure tests run with secure dummy values instead of hardcoded secrets, bypassing SonarCloud static checks."""
    settings.confluence_url = "https://test.local"
    settings.confluence_username = "dummy-user"
    settings.confluence_api_token = "dummy-token"
    settings.openai_api_key = "dummy-openai-key"
    settings.chroma_db_path = "chroma_db_test"
    settings.db_path = "jobs_test.db"

@pytest.fixture(autouse=True)
def mock_httpx_client(mocker):
    """Mocks the shared HTTP client from the confluence service to isolate tests."""
    mock_client = mocker.AsyncMock()
    # Replace global _client with our mock instance
    mocker.patch("src.confluence_summarizer.services.confluence._client", mock_client)
    yield mock_client

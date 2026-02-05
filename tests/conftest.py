import os
import pytest

# Set environment variables before any tests are collected/run
os.environ["OPENAI_API_KEY"] = "sk-test-key"
os.environ["CONFLUENCE_URL"] = "https://test.atlassian.net/wiki"
os.environ["CONFLUENCE_USERNAME"] = "testuser"
os.environ["CONFLUENCE_API_TOKEN"] = "testtoken"
os.environ["CHROMA_DB_PATH"] = "./test_chroma_db"
os.environ["DB_PATH"] = ":memory:"


@pytest.fixture(scope="session", autouse=True)
def set_env_fixture():
    # Double check/ensure they are set if overwritten
    os.environ["OPENAI_API_KEY"] = "sk-test-key"

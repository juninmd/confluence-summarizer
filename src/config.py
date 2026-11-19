from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings.

    These are read from environment variables or .env file.
    """

    CONFLUENCE_URL: str
    CONFLUENCE_USERNAME: str
    CONFLUENCE_API_TOKEN: str
    OPENAI_API_KEY: str = (
        ""  # Default empty to allow tests and environments without LLM
    )
    # OpenAI-compatible endpoints (vLLM, Ollama, TEI...). None = api.openai.com
    LLM_BASE_URL: str | None = None
    LLM_MODEL: str = "Qwen/Qwen3-32B"
    EMBEDDING_BASE_URL: str | None = None
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/confluence"
    BACKUP_DIR: str = "backup"
    BACKUP_CONCURRENCY: int = 5
    DUPLICATE_THRESHOLD: float = 0.85
    DB_PATH: str = "jobs.db"
    REDIS_URL: str | None = None
    INGESTION_CONCURRENCY: int = 10
    REFINEMENT_CONCURRENCY: int = 5
    APP_API_KEY: str
    ALLOWED_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(env_file="secrets/.env")


# Required fields (CONFLUENCE_*, APP_API_KEY) come from the environment or secrets/.env;
# tests set them in tests/conftest.py. Never pass them as init kwargs: those would override the env.
settings = Settings()  # pyright: ignore[reportCallIssue]

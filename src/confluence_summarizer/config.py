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
    CHROMA_DB_PATH: str = "chroma_db"
    DB_PATH: str = "jobs.db"
    REDIS_URL: str | None = None
    INGESTION_CONCURRENCY: int = 10
    REFINEMENT_CONCURRENCY: int = 5
    APP_API_KEY: str
    ALLOWED_ORIGINS: list[str] = []

    model_config = SettingsConfigDict(env_file=".env")


# For tests or default load, provide empty defaults
settings = Settings(
    CONFLUENCE_URL="https://dummy.local",
    CONFLUENCE_USERNAME="dummy-user",
    CONFLUENCE_API_TOKEN="dummy-token",
    APP_API_KEY="dummy-api-key",
)

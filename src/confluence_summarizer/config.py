from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configurações da aplicação.
    """
    confluence_url: str = "https://dummy.local"
    confluence_username: str = "dummy-user"
    confluence_api_token: str = "dummy-token"
    openai_api_key: str = "sk-dummy"
    chroma_db_path: str = "chroma_db"
    db_path: str = "jobs.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

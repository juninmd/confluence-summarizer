from pydantic_settings import BaseSettings, SettingsConfigDict





class Settings(BaseSettings):
    CONFLUENCE_URL: str = "https://dummy.local"
    CONFLUENCE_USERNAME: str = "dummy"
    CONFLUENCE_API_TOKEN: str = "dummy"
    OPENAI_API_KEY: str = "dummy-openai-key"
    CHROMA_DB_PATH: str = "./chroma_db"
    DB_PATH: str = "./jobs.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

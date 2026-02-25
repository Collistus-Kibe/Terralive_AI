from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    PROJECT_NAME: str = "TerraLive API"
    TIDB_URL: str = ""
    ELASTIC_URL: str = ""
    ELASTIC_API_KEY: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GEMINI_API_KEY: str = ""
    FIREBASE_CREDENTIALS: str = ""

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

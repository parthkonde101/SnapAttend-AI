"""Application configuration loaded from environment variables."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    All values are sourced from environment variables (or a local .env
    file during development). See `.env.example` for the full list of
    supported variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "SnapAttend"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://snapattend:snapattend@localhost:5432/snapattend"

    # JWT / security
    SECRET_KEY: str = "change-this-to-a-long-random-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    # CORS
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # File storage. Attendance photos are stored on local disk for now
    # (no processing) — this will move to object storage once OCR / AI
    # verification is implemented.
    UPLOAD_DIR: str = "uploads/attendance-photos"

    # Where registration ID-card captures are stored once they pass the
    # image quality gate (see app/ai/pipeline.py). Development only.
    REGISTRATION_UPLOAD_DIR: str = "uploads/registration-photos"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance so the environment is parsed once."""
    return Settings()


settings = get_settings()

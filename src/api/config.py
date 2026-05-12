"""Application settings sourced from environment variables.

Pydantic-Settings reads from ``REST_API_*`` env vars (case-insensitive) AND
from an optional ``.env`` file. Tests inject a fresh ``Settings`` instance
per test so configuration is never globally mutated.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REST_API_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./dev.sqlite",
        description="SQLAlchemy connection URL. Defaults to a local SQLite file.",
    )

    # Auth
    jwt_secret: str = Field(default="dev-secret-change-me", min_length=8)
    jwt_algorithm: str = Field(default="HS256")
    access_token_minutes: int = Field(default=15, gt=0)
    refresh_token_days: int = Field(default=14, gt=0)

    # Telemetry
    otel_service_name: str = Field(default="rest-api-template")
    otel_enabled: bool = Field(default=False)

    # CORS
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

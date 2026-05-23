"""Application settings sourced from environment variables.

Pydantic-Settings reads from ``REST_API_*`` env vars (case-insensitive) AND
from an optional ``.env`` file. Tests inject a fresh ``Settings`` instance
per test so configuration is never globally mutated.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Insecure dev defaults that must not survive to production.
_DEV_JWT_SECRET = "dev-secret-change-me"
_DEV_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]


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

    # Deployment environment. When set to "production" the validator below
    # refuses any of the insecure dev defaults.
    environment: str = Field(default="development")

    # Auth
    jwt_secret: str = Field(default=_DEV_JWT_SECRET, min_length=8)
    jwt_algorithm: str = Field(default="HS256")
    access_token_minutes: int = Field(default=15, gt=0)
    refresh_token_days: int = Field(default=14, gt=0)

    # Telemetry
    otel_service_name: str = Field(default="rest-api-template")
    otel_enabled: bool = Field(default=False)

    # CORS. Default permits common local-frontend dev ports only; production
    # must set REST_API_CORS_ORIGINS explicitly.
    cors_origins: list[str] = Field(default_factory=lambda: list(_DEV_CORS_ORIGINS))

    @model_validator(mode="after")
    def _no_dev_defaults_in_production(self) -> "Settings":
        if self.environment.lower() != "production":
            return self
        problems: list[str] = []
        if self.jwt_secret == _DEV_JWT_SECRET:
            problems.append(
                "REST_API_JWT_SECRET must be set to a real secret in production; "
                "the dev default 'dev-secret-change-me' is rejected."
            )
        if "*" in self.cors_origins:
            problems.append(
                "REST_API_CORS_ORIGINS must not contain '*' in production; "
                "set an explicit allowlist."
            )
        if problems:
            raise ValueError(" ".join(problems))
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

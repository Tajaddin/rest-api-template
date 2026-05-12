"""Pytest fixtures: fresh app + DB per test."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings, get_settings
from api.db.session import drop_all, init_engine


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    db = tmp_path / "test.sqlite"
    s = Settings(
        database_url=f"sqlite:///{db.as_posix()}",
        jwt_secret="test-secret-very-long-string",
        access_token_minutes=15,
        refresh_token_days=14,
        otel_enabled=False,
    )
    return s


@pytest.fixture()
def app(settings):
    # override the cached settings so the app's dependency injection works
    get_settings.cache_clear()
    os.environ["REST_API_DATABASE_URL"] = settings.database_url
    os.environ["REST_API_JWT_SECRET"] = settings.jwt_secret
    init_engine(settings)
    drop_all()
    app = create_app(settings, create_tables=True)
    yield app
    drop_all()
    get_settings.cache_clear()


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)

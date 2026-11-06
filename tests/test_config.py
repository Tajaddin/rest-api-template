"""Settings + env-var loading tests."""

from __future__ import annotations

import os

from api.config import Settings


def test_default_settings_are_safe_for_local_dev():
    s = Settings()
    assert s.database_url.startswith("sqlite")
    assert len(s.jwt_secret) >= 8


def test_env_prefix_overrides(monkeypatch):
    monkeypatch.setenv("REST_API_JWT_SECRET", "y" * 16)
    monkeypatch.setenv("REST_API_ACCESS_TOKEN_MINUTES", "60")
    s = Settings()
    assert s.jwt_secret == "y" * 16
    assert s.access_token_minutes == 60


def test_settings_rejects_short_jwt_secret():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(jwt_secret="short")


def test_unset_jwt_secret_is_random_not_the_public_dev_value(monkeypatch):
    monkeypatch.delenv("REST_API_JWT_SECRET", raising=False)
    s = Settings()
    assert s.jwt_secret != "dev-secret-change-me"
    assert len(s.jwt_secret) >= 32
    # Stable within the process, so every Settings() instance verifies the same tokens.
    assert Settings().jwt_secret == s.jwt_secret


def test_token_forged_with_old_dev_secret_is_rejected(monkeypatch, tmp_path):
    import time

    import jwt
    from fastapi.testclient import TestClient

    from api.app import create_app
    from api.config import get_settings

    monkeypatch.delenv("REST_API_JWT_SECRET", raising=False)
    s = Settings(database_url=f"sqlite:///{(tmp_path / 'f.sqlite').as_posix()}")
    app = create_app(s)
    app.dependency_overrides[get_settings] = lambda: s
    c = TestClient(app)
    c.post("/register", json={"email": "victim@example.com", "password": "correct horse"})
    forged = jwt.encode(
        {"sub": "1", "type": "access", "exp": int(time.time()) + 3600},
        "dev-secret-change-me",
        algorithm="HS256",
    )
    assert c.get("/me", headers={"authorization": f"Bearer {forged}"}).status_code == 401


def test_production_requires_an_explicit_jwt_secret(monkeypatch):
    import pytest
    from pydantic import ValidationError

    monkeypatch.delenv("REST_API_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="REST_API_JWT_SECRET"):
        Settings(environment="production")
    with pytest.raises(ValidationError, match="REST_API_JWT_SECRET"):
        Settings(environment="production", jwt_secret="dev-secret-change-me")
    assert Settings(environment="production", jwt_secret="z" * 32).jwt_secret == "z" * 32

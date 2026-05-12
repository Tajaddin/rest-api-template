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

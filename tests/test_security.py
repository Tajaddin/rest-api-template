"""Unit tests for password hashing + JWT issue/decode."""

from __future__ import annotations

import datetime as _dt

import jwt
import pytest

from api.config import Settings
from api.services.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    new_refresh_token_value,
    verify_password,
)


def test_password_hash_and_verify_roundtrip():
    h = hash_password("hunter2-strong-password")
    assert verify_password("hunter2-strong-password", h) is True
    assert verify_password("wrong-password", h) is False


def test_verify_handles_corrupt_hash_gracefully():
    assert verify_password("anything", "not-a-real-hash") is False


def test_access_token_decode_roundtrip():
    s = Settings(jwt_secret="x" * 32, access_token_minutes=15)
    tok = create_access_token(user_id=42, settings=s)
    payload = decode_access_token(tok, s)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert "exp" in payload and "iat" in payload


def test_access_token_expires():
    s = Settings(jwt_secret="x" * 32, access_token_minutes=1)
    past = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(minutes=5)
    tok = create_access_token(user_id=1, settings=s, now=past)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(tok, s)


def test_wrong_secret_rejects():
    s_signer = Settings(jwt_secret="a" * 32)
    s_verifier = Settings(jwt_secret="b" * 32)
    tok = create_access_token(user_id=1, settings=s_signer)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(tok, s_verifier)


def test_refresh_token_values_unique():
    seen = {new_refresh_token_value() for _ in range(50)}
    assert len(seen) == 50

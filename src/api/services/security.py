"""Password hashing + JWT issuance.

* ``hash_password`` / ``verify_password`` use bcrypt via passlib.
* ``create_access_token`` issues a short-lived JWT with `sub`, `iat`, `exp`.
* Refresh tokens are opaque (random URL-safe strings) stored in DB so they
  can be revoked individually. They are NOT JWTs by design.
"""

from __future__ import annotations

import datetime as _dt
import secrets

import bcrypt
import jwt

from api.config import Settings


# bcrypt's input cap is 72 bytes; we truncate UTF-8 input so very long
# passwords don't raise. Truncation matches Django / Flask defaults.
_BCRYPT_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt(rounds=10)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bytes(password), hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


def create_access_token(
    *, user_id: int, settings: Settings, now: _dt.datetime | None = None
) -> str:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    exp = now + _dt.timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict:
    """Returns payload dict; raises ``jwt.InvalidTokenError`` on any failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def new_refresh_token_value() -> str:
    return secrets.token_urlsafe(48)

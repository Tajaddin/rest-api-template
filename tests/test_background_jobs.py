"""Background-job tests run synchronously via direct function calls."""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import select

from api.db.session import session_scope
from api.jobs.scheduler import cleanup_expired_refresh_tokens
from api.models.tables import RefreshToken, User
from api.services.security import hash_password


def test_cleanup_removes_only_expired(client):
    """``client`` fixture initialises the DB; we then drive jobs directly."""
    now = _dt.datetime.now(_dt.timezone.utc)
    with session_scope() as db:
        u = User(email="cleanup@example.com", password_hash=hash_password("supersecret1"))
        db.add(u)
        db.flush()
        db.add(
            RefreshToken(
                user_id=u.id, token="active-1", expires_at=now + _dt.timedelta(days=1)
            )
        )
        db.add(
            RefreshToken(
                user_id=u.id, token="expired-1", expires_at=now - _dt.timedelta(days=1)
            )
        )
        db.add(
            RefreshToken(
                user_id=u.id, token="expired-2", expires_at=now - _dt.timedelta(hours=1)
            )
        )

    deleted = cleanup_expired_refresh_tokens()
    assert deleted == 2

    with session_scope() as db:
        remaining = db.execute(select(RefreshToken)).scalars().all()
        assert {r.token for r in remaining} == {"active-1"}


def test_cleanup_is_idempotent(client):
    """Running cleanup twice in a row deletes once and reports 0 the second time."""
    now = _dt.datetime.now(_dt.timezone.utc)
    with session_scope() as db:
        u = User(email="idem@example.com", password_hash=hash_password("supersecret1"))
        db.add(u)
        db.flush()
        db.add(
            RefreshToken(
                user_id=u.id, token="expired-x", expires_at=now - _dt.timedelta(hours=1)
            )
        )
    first = cleanup_expired_refresh_tokens()
    second = cleanup_expired_refresh_tokens()
    assert first == 1
    assert second == 0

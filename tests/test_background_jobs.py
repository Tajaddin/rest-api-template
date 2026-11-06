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
                user_id=u.id, family_id="f", token_hash="active-1", expires_at=now + _dt.timedelta(days=1)
            )
        )
        db.add(
            RefreshToken(
                user_id=u.id, family_id="f", token_hash="expired-1", expires_at=now - _dt.timedelta(days=1)
            )
        )
        db.add(
            RefreshToken(
                user_id=u.id, family_id="f", token_hash="expired-2", expires_at=now - _dt.timedelta(hours=1)
            )
        )

    deleted = cleanup_expired_refresh_tokens()
    assert deleted == 2

    with session_scope() as db:
        remaining = db.execute(select(RefreshToken)).scalars().all()
        assert {r.token_hash for r in remaining} == {"active-1"}


def test_cleanup_is_idempotent(client):
    """Running cleanup twice in a row deletes once and reports 0 the second time."""
    now = _dt.datetime.now(_dt.timezone.utc)
    with session_scope() as db:
        u = User(email="idem@example.com", password_hash=hash_password("supersecret1"))
        db.add(u)
        db.flush()
        db.add(
            RefreshToken(
                user_id=u.id, family_id="f", token_hash="expired-x", expires_at=now - _dt.timedelta(hours=1)
            )
        )
    first = cleanup_expired_refresh_tokens()
    second = cleanup_expired_refresh_tokens()
    assert first == 1
    assert second == 0


def test_count_active_users_counts_only_active(client):
    from api.jobs.scheduler import count_active_users

    with session_scope() as db:
        db.add(User(email="on1@example.com", password_hash="x"))
        db.add(User(email="on2@example.com", password_hash="x"))
        db.add(User(email="off@example.com", password_hash="x", is_active=False))
    assert count_active_users() == 2


def test_app_runs_the_scheduler_for_its_lifetime(app):
    from fastapi.testclient import TestClient

    with TestClient(app):
        sched = app.state.scheduler
        assert sched.running
        assert {j.id for j in sched.get_jobs()} == {"cleanup_refresh_tokens", "active_user_count"}
    assert not sched.running

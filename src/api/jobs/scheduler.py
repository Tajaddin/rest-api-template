"""APScheduler-based background jobs.

We use APScheduler (in-process) rather than Celery so the template runs
without external infrastructure (no Redis / RabbitMQ broker). For
production use, the contract is unchanged — swap the scheduler module
for one that submits to Celery / RQ / Dramatiq.

Jobs included:
* ``cleanup_expired_refresh_tokens`` — runs every minute, hard-deletes
  refresh tokens whose ``expires_at`` is past the threshold.
* ``log_active_user_count`` — runs every 5 minutes, used as a tracing
  example.
"""

from __future__ import annotations

import datetime as _dt
import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from api.db.session import session_scope
from api.models.tables import RefreshToken, User


_log = logging.getLogger("api.jobs")


def cleanup_expired_refresh_tokens(*, now_factory: Callable[[], _dt.datetime] | None = None) -> int:
    """Delete refresh tokens whose ``expires_at`` is in the past.

    Returns the number of rows deleted. Idempotent. Safe to run from a
    cron expression or a single ``run_now`` call from a test.
    """
    now = (now_factory or (lambda: _dt.datetime.now(_dt.timezone.utc)))()
    deleted = 0
    with session_scope() as db:
        rows = db.execute(select(RefreshToken).where(RefreshToken.expires_at < now)).scalars().all()
        for rt in rows:
            db.delete(rt)
            deleted += 1
    return deleted


def count_active_users() -> int:
    with session_scope() as db:
        return int(
            db.execute(
                select(User).where(User.is_active.is_(True))
            ).scalars().unique().rowcount or len(db.execute(select(User).where(User.is_active.is_(True))).scalars().all())
        )


def build_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler()
    sched.add_job(cleanup_expired_refresh_tokens, "interval", minutes=1, id="cleanup_refresh_tokens")
    sched.add_job(
        lambda: _log.info("active_user_count=%s", count_active_users()),
        "interval",
        minutes=5,
        id="active_user_count",
    )
    return sched

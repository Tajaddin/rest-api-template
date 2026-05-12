"""SQLAlchemy engine + session factory.

The engine is constructed lazily so tests can override the database URL
before any connection is opened.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from api.config import Settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None
_url_used: str | None = None


def init_engine(settings: Settings) -> None:
    """(Re-)create the engine + sessionmaker. Idempotent per URL."""
    global _engine, _SessionLocal, _url_used
    if _url_used == settings.database_url and _engine is not None:
        return
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    _engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    _url_used = settings.database_url


def get_engine():
    if _engine is None:
        raise RuntimeError("engine not initialised; call init_engine(settings) first")
    return _engine


def create_all() -> None:
    """Create every table from `Base.metadata`. Use for tests + initial dev."""
    Base.metadata.create_all(bind=get_engine())


def drop_all() -> None:
    Base.metadata.drop_all(bind=get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    if _SessionLocal is None:
        raise RuntimeError("session factory not initialised")
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency wrapper around ``session_scope``."""
    if _SessionLocal is None:
        raise RuntimeError("session factory not initialised")
    s = _SessionLocal()
    try:
        yield s
    finally:
        s.close()

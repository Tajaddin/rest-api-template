"""ORM tables.

* :class:`User` — credentials + minimal profile.
* :class:`RefreshToken` — opaque refresh tokens with revocation tracking.
* :class:`Task` — a tiny domain entity to exercise CRUD endpoints + background jobs.
"""

from __future__ import annotations

import datetime as _dt
import secrets

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db.session import Base


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(48)
    )
    expires_at: Mapped[_dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[_dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        exp = self.expires_at
        # SQLite stores datetimes as text without tz; restore aware on read.
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=_dt.timezone.utc)
        return _utc_now() < exp


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, onupdate=_utc_now, nullable=False
    )

    owner: Mapped[User] = relationship(back_populates="tasks")

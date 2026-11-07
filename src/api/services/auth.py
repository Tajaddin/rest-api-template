"""Auth flows: register, login, refresh, logout."""

from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from api.config import Settings
from api.models.tables import RefreshToken, User
from api.services.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token_value,
    verify_password,
)


class AuthError(Exception):
    pass


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def register_user(db: Session, email: str, password: str) -> User:
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing is not None:
        raise AuthError("email already registered")
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("invalid credentials")
    if not verify_password(password, user.password_hash):
        raise AuthError("invalid credentials")
    return user


def issue_tokens(
    db: Session, user: User, settings: Settings, *, family_id: str | None = None
) -> TokenPair:
    access = create_access_token(user_id=user.id, settings=settings)
    now = _dt.datetime.now(_dt.timezone.utc)
    refresh_value = new_refresh_token_value()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4().hex,
            token_hash=hash_refresh_token(refresh_value),
            expires_at=now + _dt.timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh_value)


def _revoke(db: Session, *criteria) -> int:
    """Revoke the still-active refresh tokens matching ``criteria``; return how many."""
    return db.execute(
        update(RefreshToken)
        .where(*criteria, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_dt.datetime.now(_dt.timezone.utc))
        .execution_options(synchronize_session=False)
    ).rowcount


def rotate_refresh_token(
    db: Session, token_value: str, settings: Settings
) -> TokenPair:
    rt = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token_value))
    ).scalar_one_or_none()
    if rt is None or (rt.revoked_at is None and not rt.is_active):
        raise AuthError("invalid refresh token")
    # The conditional UPDATE lets exactly one request claim the token. A token
    # that was already rotated, or a lost race for it, means two parties hold
    # a copy, so every token from that login is revoked (RFC 9700, 4.14.2).
    if rt.revoked_at is not None or _revoke(db, RefreshToken.id == rt.id) != 1:
        _revoke(db, RefreshToken.family_id == rt.family_id)
        db.commit()
        raise AuthError("invalid refresh token")
    user = db.get(User, rt.user_id)
    if user is None or not user.is_active:
        db.commit()
        raise AuthError("user no longer active")
    # Commits the claim and the successor together.
    return issue_tokens(db, user, settings, family_id=rt.family_id)


def revoke_refresh_token(db: Session, token_value: str) -> bool:
    revoked = _revoke(db, RefreshToken.token_hash == hash_refresh_token(token_value))
    db.commit()
    return revoked == 1

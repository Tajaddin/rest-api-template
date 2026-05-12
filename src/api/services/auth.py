"""Auth flows: register, login, refresh, logout."""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import Settings
from api.models.tables import RefreshToken, User
from api.services.security import (
    create_access_token,
    hash_password,
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


def issue_tokens(db: Session, user: User, settings: Settings) -> TokenPair:
    access = create_access_token(user_id=user.id, settings=settings)
    now = _dt.datetime.now(_dt.timezone.utc)
    refresh = RefreshToken(
        user_id=user.id,
        token=new_refresh_token_value(),
        expires_at=now + _dt.timedelta(days=settings.refresh_token_days),
    )
    db.add(refresh)
    db.commit()
    db.refresh(refresh)
    return TokenPair(access_token=access, refresh_token=refresh.token)


def rotate_refresh_token(
    db: Session, token_value: str, settings: Settings
) -> TokenPair:
    rt = db.execute(
        select(RefreshToken).where(RefreshToken.token == token_value)
    ).scalar_one_or_none()
    if rt is None or not rt.is_active:
        raise AuthError("invalid refresh token")
    # rotate: revoke the old one, issue a fresh pair
    rt.revoked_at = _dt.datetime.now(_dt.timezone.utc)
    db.add(rt)
    db.commit()
    user = db.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise AuthError("user no longer active")
    return issue_tokens(db, user, settings)


def revoke_refresh_token(db: Session, token_value: str) -> bool:
    rt = db.execute(
        select(RefreshToken).where(RefreshToken.token == token_value)
    ).scalar_one_or_none()
    if rt is None or rt.revoked_at is not None:
        return False
    rt.revoked_at = _dt.datetime.now(_dt.timezone.utc)
    db.add(rt)
    db.commit()
    return True

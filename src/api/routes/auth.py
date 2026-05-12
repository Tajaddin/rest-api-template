"""Auth routes: /register, /login, /refresh, /logout, /me."""

from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from api.config import Settings, get_settings
from api.db.session import get_session
from api.models.tables import User
from api.services.auth import (
    AuthError,
    authenticate,
    issue_tokens,
    register_user,
    revoke_refresh_token,
    rotate_refresh_token,
)
from api.services.security import decode_access_token


router = APIRouter(tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool


def _user_from_bearer(
    authorization: str | None,
    db: Session,
    settings: Settings,
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(None, 1)[1].strip()
    try:
        payload = decode_access_token(token, settings)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"invalid token: {exc}") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="wrong token type")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="user not active")
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> User:
    return _user_from_bearer(authorization, db, settings)


@router.post("/register", response_model=UserOut, status_code=201)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_session),
) -> UserOut:
    try:
        user = register_user(db, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return UserOut(id=user.id, email=user.email, is_active=user.is_active)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        user = authenticate(db, body.email, body.password)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    pair = issue_tokens(db, user, settings)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    body: RefreshRequest,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> TokenResponse:
    try:
        pair = rotate_refresh_token(db, body.refresh_token, settings)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/logout", status_code=204)
def logout(
    body: RefreshRequest,
    db: Session = Depends(get_session),
) -> None:
    revoke_refresh_token(db, body.refresh_token)
    return None


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> UserOut:
    return UserOut(id=current.id, email=current.email, is_active=current.is_active)

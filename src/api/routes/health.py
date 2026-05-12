"""Liveness + readiness."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.db.session import get_session


router = APIRouter(tags=["meta"])


@router.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@router.get("/readyz")
def readyz(db: Session = Depends(get_session)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "db": "up"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "db": str(exc)[:200]}

"""Task CRUD routes — exercised by the integration test suite."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.db.session import get_session
from api.models.tables import User
from api.routes.auth import get_current_user
from api.services import tasks as task_svc


router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    done: bool | None = None


class TaskOut(BaseModel):
    id: int
    title: str
    body: str | None
    done: bool


def _serialize(t) -> TaskOut:
    return TaskOut(id=t.id, title=t.title, body=t.body, done=t.done)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(
    body: TaskCreateRequest,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
) -> TaskOut:
    t = task_svc.create_task(db, owner=current, title=body.title, body=body.body)
    return _serialize(t)


@router.get("", response_model=list[TaskOut])
def list_tasks(
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
) -> list[TaskOut]:
    return [_serialize(t) for t in task_svc.list_tasks(db, owner=current)]


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
) -> TaskOut:
    t = task_svc.get_task(db, owner=current, task_id=task_id)
    if t is None:
        raise HTTPException(status_code=404, detail="not found")
    return _serialize(t)


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    body: TaskUpdateRequest,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
) -> TaskOut:
    t = task_svc.update_task(
        db,
        owner=current,
        task_id=task_id,
        title=body.title,
        body=body.body,
        done=body.done,
    )
    if t is None:
        raise HTTPException(status_code=404, detail="not found")
    return _serialize(t)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_session),
    current: User = Depends(get_current_user),
) -> None:
    ok = task_svc.delete_task(db, owner=current, task_id=task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not found")
    return None

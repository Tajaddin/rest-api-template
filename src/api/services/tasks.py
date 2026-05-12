"""Task CRUD service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.models.tables import Task, User


def create_task(db: Session, *, owner: User, title: str, body: str | None = None) -> Task:
    task = Task(owner_id=owner.id, title=title, body=body)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def list_tasks(db: Session, *, owner: User) -> list[Task]:
    return list(
        db.execute(
            select(Task).where(Task.owner_id == owner.id).order_by(Task.created_at.desc())
        ).scalars()
    )


def get_task(db: Session, *, owner: User, task_id: int) -> Task | None:
    return db.execute(
        select(Task).where(Task.id == task_id, Task.owner_id == owner.id)
    ).scalar_one_or_none()


def update_task(
    db: Session,
    *,
    owner: User,
    task_id: int,
    title: str | None = None,
    body: str | None = None,
    done: bool | None = None,
) -> Task | None:
    task = get_task(db, owner=owner, task_id=task_id)
    if task is None:
        return None
    if title is not None:
        task.title = title
    if body is not None:
        task.body = body
    if done is not None:
        task.done = done
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, *, owner: User, task_id: int) -> bool:
    task = get_task(db, owner=owner, task_id=task_id)
    if task is None:
        return False
    db.delete(task)
    db.commit()
    return True

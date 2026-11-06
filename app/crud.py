"""Общие операции над записями: поиск с 404, применение PATCH, commit с 409."""

from typing import TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.logging_config import get_logger

ModelT = TypeVar("ModelT", bound=Base)

logger = get_logger("crud")

# Понятные сообщения для ограничений БД (имена заданы naming convention в app/database.py).
CONSTRAINT_MESSAGES = {
    "uq_users_email": "User with this email already exists",
    "uq_labels_name": "Label with this name already exists",
    "fk_tasks_project_id_projects": "Project does not exist",
    "fk_tasks_assignee_id_users": "Assignee (user) does not exist",
    "fk_tasks_label_id_labels": "Label does not exist",
    "fk_comments_task_id_tasks": "Task does not exist",
    "fk_comments_author_id_users": "Author (user) does not exist",
}


def get_or_404(db: Session, model: type[ModelT], obj_id: int) -> ModelT:
    obj = db.get(model, obj_id)
    if obj is None:
        logger.warning("%s id=%s not found", model.__name__, obj_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} not found",
        )
    logger.debug("Loaded %s id=%s", model.__name__, obj_id)
    return obj


def commit_or_409(db: Session, conflict_detail: str | None = None) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        detail = conflict_detail or CONSTRAINT_MESSAGES.get(
            constraint or "", "Duplicate value or invalid reference"
        )
        logger.warning("Database conflict (constraint=%s): %s", constraint, detail)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc


def create(db: Session, model: type[ModelT], payload: BaseModel) -> ModelT:
    obj = model(**payload.model_dump())
    db.add(obj)
    commit_or_409(db)
    db.refresh(obj)
    logger.info("Created %s id=%s", model.__name__, obj_id(obj))
    return obj


def update(db: Session, obj: ModelT, payload: BaseModel) -> ModelT:
    changes = payload.model_dump(exclude_unset=True)
    logger.debug("Updating %s id=%s fields=%s", type(obj).__name__, obj_id(obj), sorted(changes))
    for field, value in changes.items():
        setattr(obj, field, value)
    commit_or_409(db)
    db.refresh(obj)
    logger.info("Updated %s id=%s", type(obj).__name__, obj_id(obj))
    return obj


def delete(db: Session, obj: Base, conflict_detail: str | None = None) -> None:
    name, pk = type(obj).__name__, obj_id(obj)
    db.delete(obj)
    commit_or_409(db, conflict_detail)
    logger.info("Deleted %s id=%s", name, pk)


def obj_id(obj: Base) -> object:
    return getattr(obj, "id", None)

from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from app import crud, models, schemas
from app.database import DbSession
from app.logging_config import get_logger

router = APIRouter()
logger = get_logger("routers.tasks")


@router.get("", response_model=list[schemas.TaskRead])
def list_tasks(
    db: DbSession,
    project_id: int | None = None,
    status_filter: Annotated[schemas.TaskStatus | None, Query(alias="status")] = None,
) -> Sequence[models.Task]:
    statement = select(models.Task)
    if project_id is not None:
        statement = statement.where(models.Task.project_id == project_id)
    if status_filter is not None:
        statement = statement.where(models.Task.status == status_filter)
    items = db.scalars(statement.order_by(models.Task.id)).all()
    logger.debug(
        "Listed %d tasks (project_id=%s, status=%s)", len(items), project_id, status_filter
    )
    return items


@router.get("/{task_id}", response_model=schemas.TaskRead)
def get_task(task_id: int, db: DbSession) -> models.Task:
    return crud.get_or_404(db, models.Task, task_id)


@router.post("", response_model=schemas.TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: schemas.TaskCreate, db: DbSession) -> models.Task:
    return crud.create(db, models.Task, payload)


@router.patch("/{task_id}", response_model=schemas.TaskRead)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: DbSession) -> models.Task:
    task = crud.get_or_404(db, models.Task, task_id)
    return crud.update(db, task, payload)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: DbSession) -> Response:
    task = crud.get_or_404(db, models.Task, task_id)
    crud.delete(db, task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db

router = APIRouter()


@router.get("", response_model=list[schemas.TaskRead])
def list_tasks(
    project_id: int | None = None,
    status_filter: schemas.TaskStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    statement = select(models.Task)
    if project_id is not None:
        statement = statement.where(models.Task.project_id == project_id)
    if status_filter is not None:
        statement = statement.where(models.Task.status == status_filter)
    return db.scalars(statement.order_by(models.Task.id)).all()


@router.get("/{task_id}", response_model=schemas.TaskRead)
def get_task(task_id: int, db: Session = Depends(get_db)):
    return crud.get_or_404(db, models.Task, task_id)


@router.post("", response_model=schemas.TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: schemas.TaskCreate, db: Session = Depends(get_db)):
    return crud.create(db, models.Task, payload)


@router.patch("/{task_id}", response_model=schemas.TaskRead)
def update_task(task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)):
    task = crud.get_or_404(db, models.Task, task_id)
    return crud.update(db, task, payload)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> Response:
    task = crud.get_or_404(db, models.Task, task_id)
    crud.delete(db, task)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from collections.abc import Sequence

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app import crud, models, schemas
from app.database import DbSession
from app.logging_config import get_logger

router = APIRouter()
logger = get_logger("routers.projects")


@router.get("", response_model=list[schemas.ProjectRead])
def list_projects(db: DbSession) -> Sequence[models.Project]:
    statement = select(models.Project)
    items = db.scalars(statement.order_by(models.Project.id)).all()
    logger.debug("Listed %d projects", len(items))
    return items


@router.get("/{project_id}", response_model=schemas.ProjectRead)
def get_project(project_id: int, db: DbSession) -> models.Project:
    return crud.get_or_404(db, models.Project, project_id)


@router.post("", response_model=schemas.ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: schemas.ProjectCreate, db: DbSession) -> models.Project:
    return crud.create(db, models.Project, payload)


@router.patch("/{project_id}", response_model=schemas.ProjectRead)
def update_project(
    project_id: int, payload: schemas.ProjectUpdate, db: DbSession
) -> models.Project:
    project = crud.get_or_404(db, models.Project, project_id)
    return crud.update(db, project, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: DbSession) -> Response:
    project = crud.get_or_404(db, models.Project, project_id)
    crud.delete(db, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from collections.abc import Sequence

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app import crud, models, schemas
from app.database import DbSession
from app.logging_config import get_logger

router = APIRouter()
logger = get_logger("routers.labels")


@router.get("", response_model=list[schemas.LabelRead])
def list_labels(db: DbSession) -> Sequence[models.Label]:
    statement = select(models.Label)
    items = db.scalars(statement.order_by(models.Label.id)).all()
    logger.debug("Listed %d labels", len(items))
    return items


@router.get("/{label_id}", response_model=schemas.LabelRead)
def get_label(label_id: int, db: DbSession) -> models.Label:
    return crud.get_or_404(db, models.Label, label_id)


@router.post("", response_model=schemas.LabelRead, status_code=status.HTTP_201_CREATED)
def create_label(payload: schemas.LabelCreate, db: DbSession) -> models.Label:
    return crud.create(db, models.Label, payload)


@router.patch("/{label_id}", response_model=schemas.LabelRead)
def update_label(label_id: int, payload: schemas.LabelUpdate, db: DbSession) -> models.Label:
    label = crud.get_or_404(db, models.Label, label_id)
    return crud.update(db, label, payload)


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(label_id: int, db: DbSession) -> Response:
    label = crud.get_or_404(db, models.Label, label_id)
    crud.delete(db, label)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db

router = APIRouter()


@router.get("", response_model=list[schemas.LabelRead])
def list_labels(db: Session = Depends(get_db)):
    statement = select(models.Label)
    return db.scalars(statement.order_by(models.Label.id)).all()


@router.get("/{label_id}", response_model=schemas.LabelRead)
def get_label(label_id: int, db: Session = Depends(get_db)):
    return crud.get_or_404(db, models.Label, label_id)


@router.post("", response_model=schemas.LabelRead, status_code=status.HTTP_201_CREATED)
def create_label(payload: schemas.LabelCreate, db: Session = Depends(get_db)):
    return crud.create(db, models.Label, payload)


@router.patch("/{label_id}", response_model=schemas.LabelRead)
def update_label(label_id: int, payload: schemas.LabelUpdate, db: Session = Depends(get_db)):
    label = crud.get_or_404(db, models.Label, label_id)
    return crud.update(db, label, payload)


@router.delete("/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(label_id: int, db: Session = Depends(get_db)) -> Response:
    label = crud.get_or_404(db, models.Label, label_id)
    crud.delete(db, label)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

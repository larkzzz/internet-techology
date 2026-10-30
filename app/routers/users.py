from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db

router = APIRouter()


@router.get("", response_model=list[schemas.UserRead])
def list_users(db: Session = Depends(get_db)):
    statement = select(models.User)
    return db.scalars(statement.order_by(models.User.id)).all()


@router.get("/{user_id}", response_model=schemas.UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)):
    return crud.get_or_404(db, models.User, user_id)


@router.post("", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    return crud.create(db, models.User, payload)


@router.patch("/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db)):
    user = crud.get_or_404(db, models.User, user_id)
    return crud.update(db, user, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db)) -> Response:
    user = crud.get_or_404(db, models.User, user_id)
    crud.delete(db, user, conflict_detail="User has comments and cannot be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from collections.abc import Sequence

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app import crud, models, schemas
from app.database import DbSession
from app.logging_config import get_logger

router = APIRouter()
logger = get_logger("routers.users")


@router.get("", response_model=list[schemas.UserRead])
def list_users(db: DbSession) -> Sequence[models.User]:
    statement = select(models.User)
    items = db.scalars(statement.order_by(models.User.id)).all()
    logger.debug("Listed %d users", len(items))
    return items


@router.get("/{user_id}", response_model=schemas.UserRead)
def get_user(user_id: int, db: DbSession) -> models.User:
    return crud.get_or_404(db, models.User, user_id)


@router.post("", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: schemas.UserCreate, db: DbSession) -> models.User:
    return crud.create(db, models.User, payload)


@router.patch("/{user_id}", response_model=schemas.UserRead)
def update_user(user_id: int, payload: schemas.UserUpdate, db: DbSession) -> models.User:
    user = crud.get_or_404(db, models.User, user_id)
    return crud.update(db, user, payload)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: DbSession) -> Response:
    user = crud.get_or_404(db, models.User, user_id)
    crud.delete(db, user, conflict_detail="User has comments and cannot be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

from collections.abc import Sequence

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from app import crud, models, schemas
from app.database import DbSession
from app.logging_config import get_logger

router = APIRouter()
logger = get_logger("routers.comments")


@router.get("", response_model=list[schemas.CommentRead])
def list_comments(
    db: DbSession,
    task_id: int | None = None,
) -> Sequence[models.Comment]:
    statement = select(models.Comment)
    if task_id is not None:
        statement = statement.where(models.Comment.task_id == task_id)
    items = db.scalars(statement.order_by(models.Comment.id)).all()
    logger.debug("Listed %d comments (task_id=%s)", len(items), task_id)
    return items


@router.get("/{comment_id}", response_model=schemas.CommentRead)
def get_comment(comment_id: int, db: DbSession) -> models.Comment:
    return crud.get_or_404(db, models.Comment, comment_id)


@router.post("", response_model=schemas.CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(payload: schemas.CommentCreate, db: DbSession) -> models.Comment:
    return crud.create(db, models.Comment, payload)


@router.patch("/{comment_id}", response_model=schemas.CommentRead)
def update_comment(
    comment_id: int, payload: schemas.CommentUpdate, db: DbSession
) -> models.Comment:
    comment = crud.get_or_404(db, models.Comment, comment_id)
    return crud.update(db, comment, payload)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: DbSession) -> Response:
    comment = crud.get_or_404(db, models.Comment, comment_id)
    crud.delete(db, comment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

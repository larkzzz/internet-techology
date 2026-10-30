from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db

router = APIRouter()


@router.get("", response_model=list[schemas.CommentRead])
def list_comments(
    task_id: int | None = None,
    db: Session = Depends(get_db),
):
    statement = select(models.Comment)
    if task_id is not None:
        statement = statement.where(models.Comment.task_id == task_id)
    return db.scalars(statement.order_by(models.Comment.id)).all()


@router.get("/{comment_id}", response_model=schemas.CommentRead)
def get_comment(comment_id: int, db: Session = Depends(get_db)):
    return crud.get_or_404(db, models.Comment, comment_id)


@router.post("", response_model=schemas.CommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(payload: schemas.CommentCreate, db: Session = Depends(get_db)):
    return crud.create(db, models.Comment, payload)


@router.patch("/{comment_id}", response_model=schemas.CommentRead)
def update_comment(comment_id: int, payload: schemas.CommentUpdate, db: Session = Depends(get_db)):
    comment = crud.get_or_404(db, models.Comment, comment_id)
    return crud.update(db, comment, payload)


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: Session = Depends(get_db)) -> Response:
    comment = crud.get_or_404(db, models.Comment, comment_id)
    crud.delete(db, comment)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

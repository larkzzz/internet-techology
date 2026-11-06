from datetime import datetime
from typing import Annotated, ClassVar, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

UserRole = Literal["operator", "admin"]
TaskStatus = Literal["open", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]

Color = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class InputModel(BaseModel):
    """Базовая схема входных данных: лишние и служебные поля запрещены."""

    model_config = ConfigDict(extra="forbid")


class UpdateModel(InputModel):
    """Схема PATCH: все поля необязательны, но обязательным колонкам нельзя передать null."""

    nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def forbid_null_for_required(self) -> Self:
        for field in self.model_fields_set - self.nullable_fields:
            if getattr(self, field) is None:
                raise ValueError(f"Field '{field}' cannot be null")
        return self


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- users ---


class UserCreate(InputModel):
    email: EmailStr = Field(max_length=255)
    display_name: NonEmptyText = Field(max_length=255)
    role: UserRole = "operator"


class UserUpdate(UpdateModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    display_name: NonEmptyText | None = Field(default=None, max_length=255)
    role: UserRole | None = None


class UserRead(ReadModel):
    id: int
    email: str
    display_name: str
    role: str
    created_at: datetime


# --- projects ---


class ProjectCreate(InputModel):
    name: NonEmptyText = Field(max_length=200)
    description: str | None = None


class ProjectUpdate(UpdateModel):
    nullable_fields = frozenset({"description"})

    name: NonEmptyText | None = Field(default=None, max_length=200)
    description: str | None = None


class ProjectRead(ReadModel):
    id: int
    name: str
    description: str | None
    created_at: datetime


# --- labels ---


class LabelCreate(InputModel):
    name: NonEmptyText = Field(max_length=64)
    color: Color = "#6b7280"


class LabelUpdate(UpdateModel):
    name: NonEmptyText | None = Field(default=None, max_length=64)
    color: Color | None = None


class LabelRead(ReadModel):
    id: int
    name: str
    color: str


# --- tasks ---


class TaskCreate(InputModel):
    project_id: int
    assignee_id: int | None = None
    label_id: int | None = None
    title: NonEmptyText = Field(max_length=200)
    description: str | None = None
    status: TaskStatus = "open"
    priority: TaskPriority = "medium"


class TaskUpdate(UpdateModel):
    nullable_fields = frozenset({"assignee_id", "label_id", "description"})

    project_id: int | None = None
    assignee_id: int | None = None
    label_id: int | None = None
    title: NonEmptyText | None = Field(default=None, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None


class TaskRead(ReadModel):
    id: int
    project_id: int
    assignee_id: int | None
    label_id: int | None
    title: str
    description: str | None
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime


# --- comments ---


class CommentCreate(InputModel):
    task_id: int
    author_id: int
    body: NonEmptyText


class CommentUpdate(UpdateModel):
    body: NonEmptyText | None = None


class CommentRead(ReadModel):
    id: int
    task_id: int
    author_id: int
    body: str
    created_at: datetime

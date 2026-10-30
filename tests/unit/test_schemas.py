import pytest
from pydantic import ValidationError

from app import schemas

pytestmark = pytest.mark.unit


class TestUserSchemas:
    def test_create_defaults_role_to_operator(self):
        user = schemas.UserCreate(email="a@example.com", display_name="Alice")
        assert user.role == "operator"

    def test_create_strips_display_name(self):
        user = schemas.UserCreate(email="a@example.com", display_name="  Alice  ")
        assert user.display_name == "Alice"

    @pytest.mark.parametrize(
        "payload",
        [
            {"email": "not-an-email", "display_name": "A"},
            {"email": "a@example.com", "display_name": ""},
            {"email": "a@example.com", "display_name": "   "},
            {"email": "a@example.com", "display_name": "A", "role": "boss"},
            {"email": "a@example.com", "display_name": "x" * 256},
            {"display_name": "A"},
        ],
    )
    def test_create_rejects_invalid_data(self, payload):
        with pytest.raises(ValidationError):
            schemas.UserCreate(**payload)

    @pytest.mark.parametrize("field", ["id", "created_at"])
    def test_create_rejects_service_fields(self, field):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            schemas.UserCreate(email="a@example.com", display_name="A", **{field: 1})

    def test_update_allows_empty_payload(self):
        assert schemas.UserUpdate().model_dump(exclude_unset=True) == {}

    @pytest.mark.parametrize("field", ["email", "display_name", "role"])
    def test_update_rejects_null_for_required_fields(self, field):
        with pytest.raises(ValidationError, match=f"Field '{field}' cannot be null"):
            schemas.UserUpdate(**{field: None})


class TestProjectSchemas:
    def test_create_description_is_optional(self):
        project = schemas.ProjectCreate(name="API")
        assert project.description is None

    def test_create_requires_name(self):
        with pytest.raises(ValidationError):
            schemas.ProjectCreate(description="no name")

    def test_create_limits_name_length(self):
        with pytest.raises(ValidationError):
            schemas.ProjectCreate(name="x" * 201)

    def test_update_allows_null_description(self):
        update = schemas.ProjectUpdate(description=None)
        assert update.model_dump(exclude_unset=True) == {"description": None}

    def test_update_rejects_null_name(self):
        with pytest.raises(ValidationError):
            schemas.ProjectUpdate(name=None)


class TestLabelSchemas:
    def test_create_has_default_color(self):
        assert schemas.LabelCreate(name="bug").color == "#6b7280"

    @pytest.mark.parametrize("color", ["#FFFFFF", "#00ff7a", "#a1B2c3"])
    def test_accepts_valid_colors(self, color):
        assert schemas.LabelCreate(name="bug", color=color).color == color

    @pytest.mark.parametrize("color", ["red", "#fff", "#1234567", "123456", "#gggggg"])
    def test_rejects_invalid_colors(self, color):
        with pytest.raises(ValidationError):
            schemas.LabelCreate(name="bug", color=color)

    def test_update_rejects_null_color(self):
        with pytest.raises(ValidationError):
            schemas.LabelUpdate(color=None)


class TestTaskSchemas:
    def test_create_defaults(self):
        task = schemas.TaskCreate(project_id=1, title="Do it")
        assert task.status == "open"
        assert task.priority == "medium"
        assert task.assignee_id is None
        assert task.label_id is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"title": "no project"},
            {"project_id": 1},
            {"project_id": 1, "title": ""},
            {"project_id": 1, "title": "x", "status": "closed"},
            {"project_id": 1, "title": "x", "priority": "urgent"},
            {"project_id": "abc", "title": "x"},
        ],
    )
    def test_create_rejects_invalid_data(self, payload):
        with pytest.raises(ValidationError):
            schemas.TaskCreate(**payload)

    @pytest.mark.parametrize("field", ["assignee_id", "label_id", "description"])
    def test_update_allows_null_for_nullable_fields(self, field):
        update = schemas.TaskUpdate(**{field: None})
        assert update.model_dump(exclude_unset=True) == {field: None}

    @pytest.mark.parametrize("field", ["project_id", "title", "status", "priority"])
    def test_update_rejects_null_for_required_fields(self, field):
        with pytest.raises(ValidationError):
            schemas.TaskUpdate(**{field: None})

    def test_update_keeps_only_passed_fields(self):
        update = schemas.TaskUpdate(status="done")
        assert update.model_dump(exclude_unset=True) == {"status": "done"}


class TestCommentSchemas:
    def test_create_strips_body(self):
        comment = schemas.CommentCreate(task_id=1, author_id=1, body="  hi  ")
        assert comment.body == "hi"

    @pytest.mark.parametrize("body", ["", "   ", "\n\t"])
    def test_create_rejects_blank_body(self, body):
        with pytest.raises(ValidationError):
            schemas.CommentCreate(task_id=1, author_id=1, body=body)

    def test_update_cannot_move_comment_to_other_task(self):
        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            schemas.CommentUpdate(task_id=2)

    def test_update_rejects_null_body(self):
        with pytest.raises(ValidationError):
            schemas.CommentUpdate(body=None)


def test_read_schema_builds_from_orm_object():
    from app import models

    label = models.Label(id=1, name="bug", color="#ff0000")
    assert schemas.LabelRead.model_validate(label).model_dump() == {
        "id": 1,
        "name": "bug",
        "color": "#ff0000",
    }

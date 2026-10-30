from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app import crud, models, schemas

pytestmark = pytest.mark.unit


def integrity_error(constraint_name=None, with_diag=True):
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    if not with_diag:
        orig = Exception("no diag")
    return IntegrityError("INSERT ...", {}, orig)


@pytest.fixture
def db():
    return MagicMock()


class TestGetOr404:
    def test_returns_object(self, db):
        user = models.User(id=1)
        db.get.return_value = user
        assert crud.get_or_404(db, models.User, 1) is user
        db.get.assert_called_once_with(models.User, 1)

    def test_raises_404_with_model_name(self, db):
        db.get.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            crud.get_or_404(db, models.Project, 42)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Project not found"


class TestCommitOr409:
    def test_commits(self, db):
        crud.commit_or_409(db)
        db.commit.assert_called_once()
        db.rollback.assert_not_called()

    @pytest.mark.parametrize(
        ("constraint", "message"),
        [
            ("uq_users_email", "User with this email already exists"),
            ("uq_labels_name", "Label with this name already exists"),
            ("fk_tasks_project_id_projects", "Project does not exist"),
            ("fk_comments_author_id_users", "Author (user) does not exist"),
        ],
    )
    def test_maps_known_constraint_to_message(self, db, constraint, message):
        db.commit.side_effect = integrity_error(constraint)
        with pytest.raises(HTTPException) as exc_info:
            crud.commit_or_409(db)
        db.rollback.assert_called_once()
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == message

    @pytest.mark.parametrize(
        "error",
        [integrity_error("ck_something_unknown"), integrity_error(with_diag=False)],
    )
    def test_unknown_constraint_gets_generic_message(self, db, error):
        db.commit.side_effect = error
        with pytest.raises(HTTPException) as exc_info:
            crud.commit_or_409(db)
        db.rollback.assert_called_once()
        assert exc_info.value.detail == "Duplicate value or invalid reference"

    def test_explicit_detail_overrides_mapping(self, db):
        db.commit.side_effect = integrity_error("uq_users_email")
        with pytest.raises(HTTPException) as exc_info:
            crud.commit_or_409(db, "Custom conflict")
        assert exc_info.value.detail == "Custom conflict"

    def test_does_not_leak_database_error_text(self, db):
        db.commit.side_effect = IntegrityError(
            "INSERT INTO secret_table", {}, Exception("password=123")
        )
        with pytest.raises(HTTPException) as exc_info:
            crud.commit_or_409(db)
        assert "secret_table" not in exc_info.value.detail
        assert "password" not in exc_info.value.detail


class TestCreateUpdateDelete:
    def test_create_adds_commits_and_refreshes(self, db):
        payload = schemas.ProjectCreate(name="API", description="d")
        project = crud.create(db, models.Project, payload)
        assert isinstance(project, models.Project)
        assert (project.name, project.description) == ("API", "d")
        db.add.assert_called_once_with(project)
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(project)

    def test_update_changes_only_passed_fields(self, db):
        project = models.Project(name="Old", description="keep me")
        crud.update(db, project, schemas.ProjectUpdate(name="New"))
        assert project.name == "New"
        assert project.description == "keep me"
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(project)

    def test_update_can_set_nullable_field_to_none(self, db):
        project = models.Project(name="P", description="text")
        crud.update(db, project, schemas.ProjectUpdate(description=None))
        assert project.description is None

    def test_delete_removes_and_commits(self, db):
        project = models.Project(name="P")
        crud.delete(db, project)
        db.delete.assert_called_once_with(project)
        db.commit.assert_called_once()

    def test_delete_conflict_uses_given_detail(self, db):
        db.commit.side_effect = integrity_error("fk_comments_author_id_users")
        with pytest.raises(HTTPException) as exc_info:
            crud.delete(db, models.User(), conflict_detail="User has comments")
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "User has comments"

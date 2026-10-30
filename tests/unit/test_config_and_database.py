from unittest.mock import MagicMock

import pytest

from app import database
from app.config import Settings

pytestmark = pytest.mark.unit


def test_settings_read_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg2://u:p@db:5432/x")
    assert Settings(_env_file=None).database_url == "postgresql+psycopg2://u:p@db:5432/x"


def test_settings_require_database_url(monkeypatch):
    from pydantic import ValidationError

    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_db_closes_session_after_request(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    generator = database.get_db()
    assert next(generator) is session
    session.close.assert_not_called()

    with pytest.raises(StopIteration):
        next(generator)
    session.close.assert_called_once()


def test_get_db_closes_session_on_error(monkeypatch):
    session = MagicMock()
    monkeypatch.setattr(database, "SessionLocal", lambda: session)

    generator = database.get_db()
    next(generator)
    with pytest.raises(RuntimeError):
        generator.throw(RuntimeError("boom"))
    session.close.assert_called_once()


def test_constraint_names_follow_naming_convention():
    from app import models  # noqa: F401

    names = {
        constraint.name
        for table in database.Base.metadata.tables.values()
        for constraint in table.constraints
    }
    assert {
        "uq_users_email",
        "uq_labels_name",
        "ck_users_role",
        "ck_tasks_status",
        "fk_tasks_project_id_projects",
        "fk_comments_author_id_users",
    } <= names

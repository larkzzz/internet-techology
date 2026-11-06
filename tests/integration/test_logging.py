"""Приложение пишет логи всех уровней в нужных ситуациях."""

import logging

import pytest
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app
from tests import factories

pytestmark = pytest.mark.integration


def messages(caplog, level):
    return [r.getMessage() for r in caplog.records if r.levelno == level]


def test_debug_logs_reads_and_filters(client, app_logs):
    user = factories.create_user(client)
    client.get(f"/v1/users/{user['id']}")
    client.get("/v1/tasks", params={"status": "open"})
    client.get("/health")

    debug = messages(app_logs, logging.DEBUG)
    assert f"Loaded User id={user['id']}" in debug
    assert "Listed 0 tasks (project_id=None, status=open)" in debug
    assert "Health check passed" in debug


def test_info_logs_requests_and_changes(client, app_logs):
    project = factories.create_project(client)
    client.patch(f"/v1/projects/{project['id']}", json={"name": "New"})
    client.delete(f"/v1/projects/{project['id']}")

    info = messages(app_logs, logging.INFO)
    pid = project["id"]
    assert f"Created Project id={pid}" in info
    assert f"Updated Project id={pid}" in info
    assert f"Deleted Project id={pid}" in info
    assert any(m.startswith("POST /v1/projects -> 201 (") for m in info)
    assert any(m.startswith(f"DELETE /v1/projects/{pid} -> 204 (") for m in info)


def test_lifespan_logs_start_and_stop(clean_db, app_logs):
    from fastapi.testclient import TestClient

    with TestClient(app):
        pass
    info = messages(app_logs, logging.INFO)
    assert any(m.startswith("TaskFlow API started (log_level=") for m in info)
    assert "TaskFlow API stopped" in info


def test_warning_logs_client_errors(client, app_logs):
    factories.create_user(client, email="dup@example.com")
    client.post("/v1/users", json={"email": "dup@example.com", "display_name": "X"})
    client.get("/v1/tasks/999")
    client.post("/v1/labels", json={"name": "x", "color": "red"})

    warnings = messages(app_logs, logging.WARNING)
    assert (
        "Database conflict (constraint=uq_users_email): User with this email already exists"
        in warnings
    )
    assert "Task id=999 not found" in warnings
    assert "Validation error on POST /v1/labels: body.color" in warnings


def test_validation_error_response_is_unchanged(client):
    response = client.post("/v1/labels", json={"name": "x", "color": "red"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "color"]


def test_error_logs_unhandled_exception_and_returns_500(client, app_logs):
    def broken_db():
        raise RuntimeError("secret internal details")

    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/v1/users")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert "secret" not in response.text

    errors = [r for r in app_logs.records if r.levelno == logging.ERROR]
    assert [r.getMessage() for r in errors] == ["Unhandled error on GET /v1/users"]
    assert errors[0].exc_info[0] is RuntimeError
    assert "GET /v1/users -> 500 (" in " ".join(messages(app_logs, logging.INFO))


def test_critical_logs_database_outage(client, app_logs):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        assert client.get("/health").status_code == 503
    finally:
        app.dependency_overrides.clear()

    assert messages(app_logs, logging.CRITICAL) == ["Health check failed: database is unavailable"]


def test_logs_do_not_contain_database_password(client, app_logs):
    factories.create_user(client)
    client.get("/health")
    assert "taskflow:taskflow@" not in app_logs.text

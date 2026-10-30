import pytest
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app

pytestmark = pytest.mark.integration


def test_health_checks_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_returns_503_when_database_is_down(client):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}


def test_docs_and_openapi_are_available(client):
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for resource in ("users", "projects", "labels", "tasks", "comments"):
        assert f"/v1/{resource}" in paths
        assert f"/v1/{resource}/{{{resource[:-1]}_id}}" in paths

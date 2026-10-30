"""Общие проверки пяти CRUD-операций для всех ресурсов."""

import pytest

from tests import factories

pytestmark = pytest.mark.integration


def make_users(client):
    return factories.create_user(client), {"display_name": "Renamed"}


def make_projects(client):
    return factories.create_project(client), {"name": "Renamed"}


def make_labels(client):
    return factories.create_label(client), {"color": "#123abc"}


def make_tasks(client):
    project = factories.create_project(client)
    return factories.create_task(client, project["id"]), {"status": "in_progress"}


def make_comments(client):
    user = factories.create_user(client)
    project = factories.create_project(client)
    task = factories.create_task(client, project["id"])
    return factories.create_comment(client, task["id"], user["id"]), {"body": "Edited"}


RESOURCES = {
    "users": make_users,
    "projects": make_projects,
    "labels": make_labels,
    "tasks": make_tasks,
    "comments": make_comments,
}

parametrize_resources = pytest.mark.parametrize(
    ("resource", "make"), RESOURCES.items(), ids=RESOURCES.keys()
)


@parametrize_resources
def test_list_is_empty_initially(client, resource, make):
    response = client.get(f"/v1/{resource}")
    assert response.status_code == 200
    assert response.json() == []


@parametrize_resources
def test_create_get_list(client, resource, make):
    created, _ = make(client)
    assert isinstance(created["id"], int)

    response = client.get(f"/v1/{resource}/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created

    listed = client.get(f"/v1/{resource}").json()
    assert created in listed


@parametrize_resources
def test_patch_updates_only_passed_fields(client, resource, make):
    created, changes = make(client)
    response = client.patch(f"/v1/{resource}/{created['id']}", json=changes)
    assert response.status_code == 200
    body = response.json()
    for field, value in changes.items():
        assert body[field] == value
    untouched = {k: v for k, v in created.items() if k not in changes and k != "updated_at"}
    assert {k: body[k] for k in untouched} == untouched


@parametrize_resources
def test_delete_returns_204_without_body(client, resource, make):
    created, _ = make(client)
    response = client.delete(f"/v1/{resource}/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/v1/{resource}/{created['id']}").status_code == 404


@parametrize_resources
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_record_returns_404(client, resource, make, method):
    kwargs = {"json": {}} if method == "patch" else {}
    response = getattr(client, method)(f"/v1/{resource}/999999", **kwargs)
    assert response.status_code == 404
    assert response.json()["detail"].endswith("not found")


@parametrize_resources
def test_non_integer_id_returns_422(client, resource, make):
    assert client.get(f"/v1/{resource}/abc").status_code == 422


@parametrize_resources
def test_create_with_empty_body_returns_422(client, resource, make):
    assert client.post(f"/v1/{resource}", json={}).status_code == 422


@parametrize_resources
@pytest.mark.parametrize("field", ["id", "created_at"])
def test_service_fields_are_rejected(client, resource, make, field):
    created, _ = make(client)
    response = client.patch(f"/v1/{resource}/{created['id']}", json={field: 1})
    assert response.status_code == 422


@parametrize_resources
def test_list_is_ordered_by_id(client, resource, make):
    ids = [make(client)[0]["id"] for _ in range(3)]
    listed_ids = [item["id"] for item in client.get(f"/v1/{resource}").json()]
    assert listed_ids == sorted(listed_ids)
    assert set(ids) <= set(listed_ids)

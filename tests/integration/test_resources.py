"""Поведение, специфичное для каждого ресурса: значения по умолчанию, конфликты, связи."""

import pytest

from tests import factories

pytestmark = pytest.mark.integration


class TestUsers:
    def test_defaults_and_server_fields(self, client):
        user = factories.create_user(client, email="a@example.com", display_name="Alice")
        assert user["role"] == "operator"
        assert user["created_at"]

    def test_admin_role(self, client):
        assert factories.create_user(client, role="admin")["role"] == "admin"

    def test_invalid_role_returns_422(self, client):
        response = client.post(
            "/v1/users", json={"email": "a@example.com", "display_name": "A", "role": "root"}
        )
        assert response.status_code == 422

    def test_duplicate_email_on_create_returns_409(self, client):
        factories.create_user(client, email="dup@example.com")
        response = client.post(
            "/v1/users", json={"email": "dup@example.com", "display_name": "Other"}
        )
        assert response.status_code == 409
        assert response.json() == {"detail": "User with this email already exists"}

    def test_duplicate_email_on_patch_returns_409(self, client):
        factories.create_user(client, email="taken@example.com")
        other = factories.create_user(client)
        response = client.patch(f"/v1/users/{other['id']}", json={"email": "taken@example.com"})
        assert response.status_code == 409

    def test_api_keeps_working_after_conflict(self, client):
        factories.create_user(client, email="dup@example.com")
        client.post("/v1/users", json={"email": "dup@example.com", "display_name": "X"})
        assert client.get("/v1/users").status_code == 200
        factories.create_user(client)

    def test_patch_null_for_required_field_returns_422(self, client):
        user = factories.create_user(client)
        response = client.patch(f"/v1/users/{user['id']}", json={"display_name": None})
        assert response.status_code == 422

    def test_cannot_delete_user_with_comments(self, client):
        user = factories.create_user(client)
        task = factories.create_task(client, factories.create_project(client)["id"])
        factories.create_comment(client, task["id"], user["id"])

        response = client.delete(f"/v1/users/{user['id']}")
        assert response.status_code == 409
        assert response.json() == {"detail": "User has comments and cannot be deleted"}
        assert client.get(f"/v1/users/{user['id']}").status_code == 200

    def test_deleting_assignee_clears_tasks(self, client):
        user = factories.create_user(client)
        task = factories.create_task(
            client, factories.create_project(client)["id"], assignee_id=user["id"]
        )
        assert client.delete(f"/v1/users/{user['id']}").status_code == 204
        assert client.get(f"/v1/tasks/{task['id']}").json()["assignee_id"] is None


class TestProjects:
    def test_description_optional_and_clearable(self, client):
        project = factories.create_project(client, description="text")
        response = client.patch(f"/v1/projects/{project['id']}", json={"description": None})
        assert response.status_code == 200
        assert response.json()["description"] is None

    def test_too_long_name_returns_422(self, client):
        assert client.post("/v1/projects", json={"name": "x" * 201}).status_code == 422

    def test_delete_cascades_to_tasks_and_comments(self, client):
        user = factories.create_user(client)
        project = factories.create_project(client)
        other_project = factories.create_project(client)
        task = factories.create_task(client, project["id"])
        other_task = factories.create_task(client, other_project["id"])
        factories.create_comment(client, task["id"], user["id"])
        other_comment = factories.create_comment(client, other_task["id"], user["id"])

        assert client.delete(f"/v1/projects/{project['id']}").status_code == 204

        assert client.get(f"/v1/tasks/{task['id']}").status_code == 404
        assert client.get("/v1/tasks").json() == [other_task]
        assert client.get("/v1/comments").json() == [other_comment]
        assert client.get(f"/v1/users/{user['id']}").status_code == 200


class TestLabels:
    def test_default_color(self, client):
        assert factories.create_label(client)["color"] == "#6b7280"

    @pytest.mark.parametrize("color", ["red", "#12345", "#zzzzzz"])
    def test_invalid_color_returns_422(self, client, color):
        assert client.post("/v1/labels", json={"name": "x", "color": color}).status_code == 422

    def test_duplicate_name_returns_409(self, client):
        factories.create_label(client, name="bug")
        response = client.post("/v1/labels", json={"name": "bug"})
        assert response.status_code == 409
        assert response.json() == {"detail": "Label with this name already exists"}

    def test_deleting_label_clears_tasks(self, client):
        label = factories.create_label(client)
        task = factories.create_task(
            client, factories.create_project(client)["id"], label_id=label["id"]
        )
        assert client.delete(f"/v1/labels/{label['id']}").status_code == 204
        assert client.get(f"/v1/tasks/{task['id']}").json()["label_id"] is None


class TestTasks:
    def test_defaults(self, client):
        task = factories.create_task(client, factories.create_project(client)["id"])
        assert task["status"] == "open"
        assert task["priority"] == "medium"
        assert task["assignee_id"] is None
        assert task["label_id"] is None
        assert task["created_at"] == task["updated_at"]

    def test_create_with_all_references(self, client):
        user = factories.create_user(client)
        label = factories.create_label(client)
        project = factories.create_project(client)
        task = factories.create_task(
            client,
            project["id"],
            assignee_id=user["id"],
            label_id=label["id"],
            priority="high",
            description="details",
        )
        assert (task["assignee_id"], task["label_id"]) == (user["id"], label["id"])
        assert task["priority"] == "high"

    @pytest.mark.parametrize(
        ("field", "message"),
        [
            ("project_id", "Project does not exist"),
            ("assignee_id", "Assignee (user) does not exist"),
            ("label_id", "Label does not exist"),
        ],
    )
    def test_invalid_reference_returns_409(self, client, field, message):
        project = factories.create_project(client)
        payload = {"project_id": project["id"], "title": "x", field: 999999}
        response = client.post("/v1/tasks", json=payload)
        assert response.status_code == 409
        assert response.json() == {"detail": message}

    def test_patch_invalid_reference_returns_409(self, client):
        task = factories.create_task(client, factories.create_project(client)["id"])
        response = client.patch(f"/v1/tasks/{task['id']}", json={"assignee_id": 999999})
        assert response.status_code == 409

    @pytest.mark.parametrize(
        "payload", [{"status": "closed"}, {"priority": "urgent"}, {"title": ""}, {"title": None}]
    )
    def test_patch_invalid_values_return_422(self, client, payload):
        task = factories.create_task(client, factories.create_project(client)["id"])
        assert client.patch(f"/v1/tasks/{task['id']}", json=payload).status_code == 422

    def test_patch_status_to_done_updates_timestamp(self, client):
        task = factories.create_task(client, factories.create_project(client)["id"])
        response = client.patch(f"/v1/tasks/{task['id']}", json={"status": "done"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "done"
        assert body["updated_at"] > task["updated_at"]
        assert body["created_at"] == task["created_at"]

    def test_patch_can_move_task_to_other_project(self, client):
        task = factories.create_task(client, factories.create_project(client)["id"])
        other = factories.create_project(client)
        response = client.patch(f"/v1/tasks/{task['id']}", json={"project_id": other["id"]})
        assert response.json()["project_id"] == other["id"]

    def test_delete_cascades_to_comments(self, client):
        user = factories.create_user(client)
        task = factories.create_task(client, factories.create_project(client)["id"])
        comment = factories.create_comment(client, task["id"], user["id"])
        assert client.delete(f"/v1/tasks/{task['id']}").status_code == 204
        assert client.get(f"/v1/comments/{comment['id']}").status_code == 404


class TestTaskFilters:
    @pytest.fixture
    def tasks(self, client):
        p1 = factories.create_project(client)["id"]
        p2 = factories.create_project(client)["id"]
        return {
            "p1": p1,
            "p2": p2,
            "p1_open": factories.create_task(client, p1),
            "p1_done": factories.create_task(client, p1, status="done"),
            "p2_open": factories.create_task(client, p2),
            "p2_progress": factories.create_task(client, p2, status="in_progress"),
        }

    def ids(self, response):
        assert response.status_code == 200
        return [task["id"] for task in response.json()]

    def test_no_filters_returns_all(self, client, tasks):
        assert len(self.ids(client.get("/v1/tasks"))) == 4

    def test_filter_by_project(self, client, tasks):
        response = client.get("/v1/tasks", params={"project_id": tasks["p1"]})
        assert self.ids(response) == [tasks["p1_open"]["id"], tasks["p1_done"]["id"]]

    def test_filter_by_status(self, client, tasks):
        response = client.get("/v1/tasks", params={"status": "open"})
        assert self.ids(response) == [tasks["p1_open"]["id"], tasks["p2_open"]["id"]]

    def test_filter_by_project_and_status(self, client, tasks):
        response = client.get("/v1/tasks", params={"project_id": tasks["p2"], "status": "open"})
        assert self.ids(response) == [tasks["p2_open"]["id"]]

    def test_filter_without_matches(self, client, tasks):
        response = client.get("/v1/tasks", params={"project_id": tasks["p1"], "status": "in_progress"})
        assert self.ids(response) == []

    def test_unknown_project_returns_empty_list(self, client, tasks):
        assert self.ids(client.get("/v1/tasks", params={"project_id": 999999})) == []

    @pytest.mark.parametrize("params", [{"status": "closed"}, {"project_id": "abc"}])
    def test_invalid_filter_returns_422(self, client, tasks, params):
        assert client.get("/v1/tasks", params=params).status_code == 422


class TestComments:
    def test_blank_body_returns_422(self, client):
        user = factories.create_user(client)
        task = factories.create_task(client, factories.create_project(client)["id"])
        response = client.post(
            "/v1/comments", json={"task_id": task["id"], "author_id": user["id"], "body": "  "}
        )
        assert response.status_code == 422

    @pytest.mark.parametrize(
        ("field", "message"),
        [("task_id", "Task does not exist"), ("author_id", "Author (user) does not exist")],
    )
    def test_invalid_reference_returns_409(self, client, field, message):
        user = factories.create_user(client)
        task = factories.create_task(client, factories.create_project(client)["id"])
        payload = {"task_id": task["id"], "author_id": user["id"], "body": "x", field: 999999}
        response = client.post("/v1/comments", json=payload)
        assert response.status_code == 409
        assert response.json() == {"detail": message}

    def test_patch_cannot_change_task_or_author(self, client):
        user = factories.create_user(client)
        task = factories.create_task(client, factories.create_project(client)["id"])
        comment = factories.create_comment(client, task["id"], user["id"])
        for field in ("task_id", "author_id"):
            response = client.patch(f"/v1/comments/{comment['id']}", json={field: 1})
            assert response.status_code == 422

    def test_filter_by_task(self, client):
        user = factories.create_user(client)
        project = factories.create_project(client)
        task1 = factories.create_task(client, project["id"])
        task2 = factories.create_task(client, project["id"])
        c1 = factories.create_comment(client, task1["id"], user["id"], body="first")
        c2 = factories.create_comment(client, task2["id"], user["id"])
        c3 = factories.create_comment(client, task1["id"], user["id"], body="second")

        assert client.get("/v1/comments", params={"task_id": task1["id"]}).json() == [c1, c3]
        assert client.get("/v1/comments", params={"task_id": task2["id"]}).json() == [c2]
        assert client.get("/v1/comments", params={"task_id": 999999}).json() == []
        assert client.get("/v1/comments", params={"task_id": "x"}).status_code == 422

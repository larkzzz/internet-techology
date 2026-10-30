"""Сквозной сценарий из раздела «Как проверить работу» задания."""

import pytest

pytestmark = pytest.mark.e2e


def check(response, status_code):
    assert response.status_code == status_code, response.text
    return response.json() if response.content else None


def test_full_task_lifecycle(api, unique):
    assert check(api.get("/health"), 200) == {"status": "ok", "database": "up"}
    assert api.get("/docs").status_code == 200

    # 1. Пользователь, проект и метка
    user = check(
        api.post("/v1/users", json={"email": f"e2e-{unique}@example.com", "display_name": "E2E"}),
        201,
    )
    project = check(api.post("/v1/projects", json={"name": f"E2E {unique}"}), 201)
    label = check(api.post("/v1/labels", json={"name": f"e2e-{unique}", "color": "#22c55e"}), 201)

    # 2. Задача со ссылками на них
    task = check(
        api.post(
            "/v1/tasks",
            json={
                "project_id": project["id"],
                "assignee_id": user["id"],
                "label_id": label["id"],
                "title": "Сквозная задача",
                "priority": "high",
            },
        ),
        201,
    )
    assert task["status"] == "open"

    # 3. Комментарий к задаче
    comment = check(
        api.post(
            "/v1/comments",
            json={"task_id": task["id"], "author_id": user["id"], "body": "Начинаю"},
        ),
        201,
    )

    # 4. Задача и списки с фильтрами
    assert check(api.get(f"/v1/tasks/{task['id']}"), 200) == task
    filtered = check(
        api.get("/v1/tasks", params={"project_id": project["id"], "status": "open"}), 200
    )
    assert [t["id"] for t in filtered] == [task["id"]]
    assert check(api.get("/v1/comments", params={"task_id": task["id"]}), 200) == [comment]

    # 5. Статус задачи -> done
    done = check(api.patch(f"/v1/tasks/{task['id']}", json={"status": "done"}), 200)
    assert done["status"] == "done"
    assert check(
        api.get("/v1/tasks", params={"project_id": project["id"], "status": "open"}), 200
    ) == []
    assert [
        t["id"]
        for t in check(api.get("/v1/tasks", params={"project_id": project["id"], "status": "done"}), 200)
    ] == [task["id"]]

    # Автора с комментариями удалить нельзя
    assert check(api.delete(f"/v1/users/{user['id']}"), 409)

    # 6. Удаление проекта удаляет задачи и комментарии
    assert api.delete(f"/v1/projects/{project['id']}").status_code == 204
    check(api.get(f"/v1/tasks/{task['id']}"), 404)
    check(api.get(f"/v1/comments/{comment['id']}"), 404)
    assert check(api.get("/v1/comments", params={"task_id": task["id"]}), 200) == []

    # Остальные данные на месте
    assert check(api.get(f"/v1/users/{user['id']}"), 200) == user
    assert check(api.get(f"/v1/labels/{label['id']}"), 200) == label

    # Уборка: теперь у пользователя нет комментариев, его можно удалить
    assert api.delete(f"/v1/users/{user['id']}").status_code == 204
    assert api.delete(f"/v1/labels/{label['id']}").status_code == 204


def test_error_responses_over_http(api, unique):
    check(api.get("/v1/projects/999999999"), 404)
    check(api.post("/v1/tasks", json={"title": "без проекта"}), 422)
    check(api.post("/v1/labels", json={"name": f"bad-{unique}", "color": "green"}), 422)
    check(api.post("/v1/tasks", json={"project_id": 999999999, "title": "x"}), 409)

    email = f"dup-{unique}@example.com"
    user = check(api.post("/v1/users", json={"email": email, "display_name": "A"}), 201)
    conflict = check(api.post("/v1/users", json={"email": email, "display_name": "B"}), 409)
    assert conflict == {"detail": "User with this email already exists"}
    assert api.delete(f"/v1/users/{user['id']}").status_code == 204

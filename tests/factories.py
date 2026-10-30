"""Помощники для создания записей через API в тестах."""

from itertools import count

_seq = count(1)


def create_user(client, **overrides):
    n = next(_seq)
    payload = {"email": f"user{n}@example.com", "display_name": f"User {n}"} | overrides
    response = client.post("/v1/users", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_project(client, **overrides):
    payload = {"name": f"Project {next(_seq)}"} | overrides
    response = client.post("/v1/projects", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_label(client, **overrides):
    payload = {"name": f"label-{next(_seq)}"} | overrides
    response = client.post("/v1/labels", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_task(client, project_id, **overrides):
    payload = {"project_id": project_id, "title": f"Task {next(_seq)}"} | overrides
    response = client.post("/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_comment(client, task_id, author_id, **overrides):
    payload = {"task_id": task_id, "author_id": author_id, "body": "Comment"} | overrides
    response = client.post("/v1/comments", json=payload)
    assert response.status_code == 201, response.text
    return response.json()

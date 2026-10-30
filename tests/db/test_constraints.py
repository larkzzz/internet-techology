"""Ограничения проверяются самой PostgreSQL, в обход API."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

from app import models

pytestmark = pytest.mark.db


@pytest.fixture
def conn(clean_db):
    from app.database import engine

    with engine.connect() as connection:
        yield connection
        connection.rollback()


def insert(conn, sql, **params):
    return conn.execute(text(sql), params).scalar()


def user(conn, email="a@example.com"):
    return insert(
        conn,
        "INSERT INTO users (email, display_name) VALUES (:e, 'A') RETURNING id",
        e=email,
    )


def project(conn):
    return insert(conn, "INSERT INTO projects (name) VALUES ('P') RETURNING id")


def label(conn, name="bug"):
    return insert(conn, "INSERT INTO labels (name) VALUES (:n) RETURNING id", n=name)


def task(conn, project_id, **columns):
    names = ["project_id", "title", *columns]
    values = {"project_id": project_id, "title": "T", **columns}
    sql = (
        f"INSERT INTO tasks ({', '.join(names)}) "
        f"VALUES ({', '.join(':' + n for n in names)}) RETURNING id"
    )
    return insert(conn, sql, **values)


def comment(conn, task_id, author_id, body="hi"):
    return insert(
        conn,
        "INSERT INTO comments (task_id, author_id, body) VALUES (:t, :a, :b) RETURNING id",
        t=task_id,
        a=author_id,
        b=body,
    )


def assert_violates(conn, constraint, statement):
    savepoint = conn.begin_nested()
    with pytest.raises(IntegrityError) as exc_info:
        statement()
    savepoint.rollback()
    assert exc_info.value.orig.diag.constraint_name == constraint


def scalar(conn, sql):
    return conn.execute(text(sql)).scalar()


class TestDefaults:
    def test_server_defaults(self, conn):
        user(conn)
        label(conn)
        task(conn, project(conn))
        assert scalar(conn, "SELECT role FROM users") == "operator"
        assert scalar(conn, "SELECT color FROM labels") == "#6b7280"
        assert scalar(conn, "SELECT status || '/' || priority FROM tasks") == "open/medium"
        assert scalar(conn, "SELECT created_at IS NOT NULL AND updated_at IS NOT NULL FROM tasks")
        assert scalar(conn, "SELECT created_at IS NOT NULL FROM users")


class TestUniqueAndChecks:
    def test_unique_email(self, conn):
        user(conn, "dup@example.com")
        assert_violates(conn, "uq_users_email", lambda: user(conn, "dup@example.com"))

    def test_unique_label_name(self, conn):
        label(conn, "bug")
        assert_violates(conn, "uq_labels_name", lambda: label(conn, "bug"))

    def test_role_check(self, conn):
        assert_violates(
            conn,
            "ck_users_role",
            lambda: insert(
                conn, "INSERT INTO users (email, display_name, role) VALUES ('x@e.com', 'X', 'root')"
            ),
        )

    @pytest.mark.parametrize("color", ["red", "#fff", "#gggggg", "123456#"])
    def test_color_check(self, conn, color):
        assert_violates(
            conn,
            "ck_labels_color",
            lambda: insert(conn, "INSERT INTO labels (name, color) VALUES ('x', :c)", c=color),
        )

    def test_color_longer_than_column_is_rejected(self, conn):
        savepoint = conn.begin_nested()
        with pytest.raises(DataError):
            insert(conn, "INSERT INTO labels (name, color) VALUES ('x', '#1234567')")
        savepoint.rollback()

    def test_status_check(self, conn):
        p = project(conn)
        assert_violates(conn, "ck_tasks_status", lambda: task(conn, p, status="closed"))

    def test_priority_check(self, conn):
        p = project(conn)
        assert_violates(conn, "ck_tasks_priority", lambda: task(conn, p, priority="urgent"))

    @pytest.mark.parametrize("body", ["", "   "])
    def test_comment_body_not_empty(self, conn, body):
        t = task(conn, project(conn))
        u = user(conn)
        assert_violates(conn, "ck_comments_body_not_empty", lambda: comment(conn, t, u, body))

    def test_not_null(self, conn):
        savepoint = conn.begin_nested()
        with pytest.raises(IntegrityError):
            insert(conn, "INSERT INTO projects (name) VALUES (NULL)")
        savepoint.rollback()


class TestForeignKeys:
    def test_task_requires_existing_project(self, conn):
        assert_violates(conn, "fk_tasks_project_id_projects", lambda: task(conn, 999))

    def test_task_requires_existing_assignee_and_label(self, conn):
        p = project(conn)
        assert_violates(conn, "fk_tasks_assignee_id_users", lambda: task(conn, p, assignee_id=999))
        assert_violates(conn, "fk_tasks_label_id_labels", lambda: task(conn, p, label_id=999))

    def test_comment_requires_existing_task_and_author(self, conn):
        u = user(conn)
        t = task(conn, project(conn))
        assert_violates(conn, "fk_comments_task_id_tasks", lambda: comment(conn, 999, u))
        assert_violates(conn, "fk_comments_author_id_users", lambda: comment(conn, t, 999))

    def test_project_delete_cascades(self, conn):
        u = user(conn)
        p = project(conn)
        t = task(conn, p)
        comment(conn, t, u)
        conn.execute(text("DELETE FROM projects WHERE id = :id"), {"id": p})
        assert scalar(conn, "SELECT count(*) FROM tasks") == 0
        assert scalar(conn, "SELECT count(*) FROM comments") == 0
        assert scalar(conn, "SELECT count(*) FROM users") == 1

    def test_task_delete_cascades_to_comments(self, conn):
        u = user(conn)
        t = task(conn, project(conn))
        comment(conn, t, u)
        conn.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": t})
        assert scalar(conn, "SELECT count(*) FROM comments") == 0

    def test_user_delete_sets_assignee_null(self, conn):
        u = user(conn)
        t = task(conn, project(conn), assignee_id=u)
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": u})
        assert scalar(conn, f"SELECT assignee_id FROM tasks WHERE id = {t}") is None

    def test_label_delete_sets_label_null(self, conn):
        lb = label(conn)
        t = task(conn, project(conn), label_id=lb)
        conn.execute(text("DELETE FROM labels WHERE id = :id"), {"id": lb})
        assert scalar(conn, f"SELECT label_id FROM tasks WHERE id = {t}") is None

    def test_author_with_comments_cannot_be_deleted(self, conn):
        u = user(conn)
        comment(conn, task(conn, project(conn)), u)
        assert_violates(
            conn,
            "fk_comments_author_id_users",
            lambda: conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": u}),
        )


class TestOrm:
    def test_relationships_and_updated_at(self, db_session):
        owner = models.User(email="o@example.com", display_name="Owner")
        proj = models.Project(name="P")
        lbl = models.Label(name="bug")
        tsk = models.Task(project=proj, assignee=owner, label=lbl, title="T")
        models.Comment(task=tsk, author=owner, body="hi")
        db_session.add(tsk)
        db_session.commit()

        assert proj.tasks == [tsk]
        assert owner.tasks == [tsk]
        assert lbl.tasks == [tsk]
        assert [c.body for c in tsk.comments] == ["hi"]
        assert owner.comments[0].task is tsk

        created = tsk.updated_at
        db_session.execute(text("SELECT pg_sleep(0.01)"))
        tsk.title = "Renamed"
        db_session.commit()
        db_session.refresh(tsk)
        assert tsk.updated_at > created

    def test_orm_delete_of_author_is_restricted_by_db(self, db_session):
        owner = models.User(email="o@example.com", display_name="Owner")
        tsk = models.Task(project=models.Project(name="P"), title="T")
        db_session.add(models.Comment(task=tsk, author=owner, body="hi"))
        db_session.commit()

        db_session.delete(owner)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

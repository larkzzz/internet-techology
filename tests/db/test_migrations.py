import pytest
from sqlalchemy import inspect, text

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from app.database import Base, engine
from tests.conftest import PROJECT_ROOT, TABLES, alembic_config

pytestmark = pytest.mark.db


def table_names():
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def current_revision():
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


@pytest.fixture
def at_head(migrated_db):
    """Гарантирует, что после теста схема снова на head."""
    yield
    command.upgrade(alembic_config(), "head")


def test_head_creates_exactly_five_tables(migrated_db):
    assert table_names() == set(TABLES)
    assert current_revision() == "0001"


def test_downgrade_upgrade_roundtrip(at_head):
    cfg = alembic_config()

    command.downgrade(cfg, "base")
    assert table_names() == set()
    assert current_revision() is None

    command.upgrade(cfg, "head")
    assert table_names() == set(TABLES)

    command.upgrade(cfg, "head")  # повторный upgrade ничего не делает
    assert current_revision() == "0001"


def test_models_match_migration(migrated_db):
    from app import models  # noqa: F401

    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_offline_mode_generates_sql(migrated_db, capsys):
    command.upgrade(alembic_config(), "head", sql=True)
    sql = capsys.readouterr().out
    for table in TABLES:
        assert f"CREATE TABLE {table}" in sql
    assert "ON DELETE CASCADE" in sql
    assert "ON DELETE SET NULL" in sql
    assert "ON DELETE RESTRICT" in sql


def test_env_works_without_ini_file(migrated_db):
    cfg = Config()
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    command.current(cfg)  # env.py не должен требовать alembic.ini для логирования


def test_app_does_not_create_tables_itself():
    app_sources = "".join(p.read_text() for p in (PROJECT_ROOT / "app").rglob("*.py"))
    assert "create_all" not in app_sources


def test_foreign_keys_have_required_on_delete_rules(migrated_db):
    rules = {}
    inspector = inspect(engine)
    for table in TABLES:
        for fk in inspector.get_foreign_keys(table):
            rules[(table, fk["constrained_columns"][0])] = fk["options"].get("ondelete")
    assert rules == {
        ("tasks", "project_id"): "CASCADE",
        ("tasks", "assignee_id"): "SET NULL",
        ("tasks", "label_id"): "SET NULL",
        ("comments", "task_id"): "CASCADE",
        ("comments", "author_id"): "RESTRICT",
    }


@pytest.mark.parametrize(
    ("table", "column", "type_name", "nullable"),
    [
        ("users", "email", "VARCHAR(255)", False),
        ("users", "role", "VARCHAR(32)", False),
        ("users", "created_at", "TIMESTAMP", False),
        ("projects", "name", "VARCHAR(200)", False),
        ("projects", "description", "TEXT", True),
        ("labels", "name", "VARCHAR(64)", False),
        ("labels", "color", "VARCHAR(7)", False),
        ("tasks", "project_id", "INTEGER", False),
        ("tasks", "assignee_id", "INTEGER", True),
        ("tasks", "label_id", "INTEGER", True),
        ("tasks", "status", "VARCHAR(32)", False),
        ("tasks", "priority", "VARCHAR(16)", False),
        ("tasks", "updated_at", "TIMESTAMP", False),
        ("comments", "body", "TEXT", False),
        ("comments", "author_id", "INTEGER", False),
    ],
)
def test_column_types_and_nullability(migrated_db, table, column, type_name, nullable):
    columns = {c["name"]: c for c in inspect(engine).get_columns(table)}
    assert str(columns[column]["type"]) == type_name
    assert columns[column]["nullable"] is nullable


def test_timestamps_are_timezone_aware(migrated_db):
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND data_type = 'timestamp with time zone'"
            )
        ).all()
    assert {tuple(r) for r in rows} == {
        ("users", "created_at"),
        ("projects", "created_at"),
        ("tasks", "created_at"),
        ("tasks", "updated_at"),
        ("comments", "created_at"),
    }

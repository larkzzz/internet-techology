"""Общие фикстуры.

Тесты работают только с отдельной тестовой базой (имя должно оканчиваться на `_test`):
она создаётся при необходимости, а схема в ней накатывается миграциями Alembic.
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://taskflow:taskflow@localhost:5432/taskflow_test",
)

if not make_url(TEST_DATABASE_URL).database.endswith("_test"):
    raise RuntimeError("TEST_DATABASE_URL must point to a database whose name ends with '_test'")

# Приложение читает DATABASE_URL при импорте, поэтому подменяем его до импорта app.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TABLES = ("comments", "tasks", "labels", "projects", "users")


def _ensure_database_exists(url: str) -> None:
    url = make_url(url)
    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": url.database},
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin_engine.dispose()


def alembic_config():
    from alembic.config import Config

    return Config(str(PROJECT_ROOT / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_db():
    """База с применёнными миграциями (один раз на сессию)."""
    from alembic import command

    _ensure_database_exists(TEST_DATABASE_URL)
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield
    from app.database import engine

    engine.dispose()


@pytest.fixture
def clean_db(migrated_db):
    """Очищает таблицы и сбрасывает счётчики id перед каждым тестом."""
    from app.database import engine

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db_session(clean_db):
    from app.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(clean_db):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def app_logs(caplog):
    """Перехватывает логи приложения `taskflow` (у него propagate=False) на уровне DEBUG."""
    import logging

    from app.logging_config import LOGGER_NAME

    logger = logging.getLogger(LOGGER_NAME)
    previous_level = logger.level
    logger.addHandler(caplog.handler)
    logger.setLevel(logging.DEBUG)
    yield caplog
    logger.removeHandler(caplog.handler)
    logger.setLevel(previous_level)

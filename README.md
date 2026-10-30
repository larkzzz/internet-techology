# TaskFlow API

REST API для управления задачами команды на FastAPI, PostgreSQL 16, SQLAlchemy 2 и Alembic. Запускается через Docker Compose.

## Запуск

```bash
cp .env.example .env   # при желании поменяйте пароль
docker compose up --build
```

При старте контейнер `api` дожидается готовности PostgreSQL, применяет миграции (`alembic upgrade head`) и запускает Uvicorn.

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Проверка здоровья: http://localhost:8000/health

Остановка с сохранением данных:

```bash
docker compose down
```

Полный сброс вместе с volume базы:

```bash
docker compose down -v
```

## Ресурсы

Для `users`, `projects`, `labels`, `tasks`, `comments`:

| Метод | URL | Код |
|---|---|---|
| `GET` | `/v1/{resource}` | 200 |
| `GET` | `/v1/{resource}/{id}` | 200 / 404 |
| `POST` | `/v1/{resource}` | 201 / 409 / 422 |
| `PATCH` | `/v1/{resource}/{id}` | 200 / 404 / 409 / 422 |
| `DELETE` | `/v1/{resource}/{id}` | 204 / 404 / 409 |

Фильтры: `GET /v1/tasks?project_id=1&status=open`, `GET /v1/comments?task_id=1`.

Правила удаления: задачи удаляются вместе с проектом, комментарии вместе с задачей. При удалении пользователя или метки поле `assignee_id` / `label_id` у задачи становится `NULL`. Пользователя с комментариями удалить нельзя (`409`).

## Примеры запросов

```bash
curl http://localhost:8000/health
```

```bash
curl -X POST http://localhost:8000/v1/users \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "display_name": "Alice"}'
```

```bash
curl -X POST http://localhost:8000/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "API course", "description": "Учебный проект"}'
```

```bash
curl -X POST http://localhost:8000/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "assignee_id": 1, "title": "Сделать CRUD", "priority": "high"}'
```

```bash
curl -X PATCH http://localhost:8000/v1/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"status": "done"}'
```

```bash
curl "http://localhost:8000/v1/tasks?project_id=1&status=done"
```

## Миграции

Внутри контейнера:

```bash
docker compose exec api alembic current
docker compose exec api alembic downgrade base
docker compose exec api alembic upgrade head
```

Локально (PostgreSQL должен быть доступен, `DATABASE_URL` берётся из окружения или `.env`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql+psycopg2://taskflow:taskflow@localhost:5432/taskflow
alembic upgrade head
uvicorn app.main:app --reload
```

## Тесты

Тесты написаны на pytest и разделены на четыре группы:

| Папка | Маркер | Что проверяет |
|---|---|---|
| `tests/unit` | `unit` | Pydantic-схемы, `crud`, настройки и сессию БД на моках, без PostgreSQL |
| `tests/integration` | `integration` | все эндпоинты через `TestClient` на реальной БД: коды 200/201/204/404/409/422, фильтры, каскады |
| `tests/db` | `db` | миграции (upgrade/downgrade, совпадение с моделями, offline-режим), типы колонок, `UNIQUE`, `CHECK`, `CASCADE` / `SET NULL` / `RESTRICT` прямо в PostgreSQL |
| `tests/e2e` | `e2e` | полный сценарий из задания по HTTP на запущенном Uvicorn |

Покрытие кода `app/` и `alembic/` (включая ветвления) обязано быть 100%, иначе `pytest` завершится с ошибкой.

Тесты используют отдельную базу `taskflow_test` (создаётся автоматически) и откажутся запускаться, если имя базы не оканчивается на `_test`, поэтому данные из основной базы не пострадают.

Запуск в Docker одной командой:

```bash
docker compose --profile test run --rm --build tests
```

Только одна группа:

```bash
docker compose --profile test run --rm --build tests pytest -m unit --no-cov
```

E2E против уже запущенного `docker compose up` API:

```bash
docker compose --profile test run --rm --build -e E2E_BASE_URL=http://api:8000 tests pytest tests/e2e --no-cov
```

Локально (нужен PostgreSQL на `localhost:5432`):

```bash
pip install -r requirements-dev.txt
export TEST_DATABASE_URL=postgresql+psycopg2://taskflow:taskflow@localhost:5432/taskflow_test
pytest
```

## Структура

```text
app/
  main.py        # приложение, /health, подключение роутеров
  config.py      # настройки из окружения
  database.py    # engine, сессии, Base
  models.py      # ORM-модели
  schemas.py     # Pydantic-схемы запросов и ответов
  crud.py        # общие операции: 404, PATCH, обработка конфликтов БД (409)
  routers/       # users, projects, labels, tasks, comments
alembic/versions/0001_initial_schema.py
tests/
  unit/ integration/ db/ e2e/
```

import os
import socket
import threading
import time
import uuid

import httpx
import pytest
import uvicorn


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url(migrated_db):
    """Адрес работающего API.

    По умолчанию поднимает настоящий Uvicorn с приложением на свободном порту.
    Если задан E2E_BASE_URL (например, http://localhost:8000 для docker compose),
    тесты идут на этот адрес.
    """
    external = os.environ.get("E2E_BASE_URL")
    if external:
        yield external.rstrip("/")
        return

    from app.main import app

    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", ws="none")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("Uvicorn did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def api(live_server_url):
    with httpx.Client(base_url=live_server_url, timeout=10) as client:
        yield client


@pytest.fixture
def unique():
    """Уникальный суффикс, чтобы e2e не конфликтовали с уже существующими данными."""
    return uuid.uuid4().hex[:8]

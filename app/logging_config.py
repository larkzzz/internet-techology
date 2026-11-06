"""Настройка логирования приложения через переменные окружения LOG_LEVEL и LOG_FORMAT."""

import json
import logging
import sys
from datetime import UTC, datetime

LOGGER_NAME = "taskflow"

TEXT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


class JsonFormatter(logging.Formatter):
    """Одна запись лога — одна JSON-строка (удобно для сборщиков логов)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO", log_format: str = "text") -> logging.Logger:
    """Настраивает корневой логгер приложения `taskflow`; повторный вызов заменяет настройки."""
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter() if log_format == "json" else logging.Formatter(TEXT_FORMAT)
    handler.setFormatter(formatter)

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}")

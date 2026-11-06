import json
import logging

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.logging_config import LOGGER_NAME, JsonFormatter, get_logger, setup_logging

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def restore_app_logger():
    logger = logging.getLogger(LOGGER_NAME)
    saved = (list(logger.handlers), logger.level, logger.propagate)
    yield
    logger.handlers, logger.level, logger.propagate = saved


class TestSettings:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        settings = Settings(_env_file=None)
        assert (settings.log_level, settings.log_format) == ("INFO", "text")

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("debug", "DEBUG"), (" Warning ", "WARNING"), ("CRITICAL", "CRITICAL")],
    )
    def test_log_level_is_case_insensitive(self, monkeypatch, raw, expected):
        monkeypatch.setenv("LOG_LEVEL", raw)
        assert Settings(_env_file=None).log_level == expected

    def test_log_format_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "JSON")
        assert Settings(_env_file=None).log_format == "json"

    @pytest.mark.parametrize(("name", "value"), [("LOG_LEVEL", "verbose"), ("LOG_FORMAT", "xml")])
    def test_invalid_values_are_rejected(self, monkeypatch, name, value):
        monkeypatch.setenv(name, value)
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


class TestSetupLogging:
    def test_text_format(self, capsys):
        setup_logging("INFO", "text")
        get_logger("test").info("hello %s", "world")
        line = capsys.readouterr().out.strip()
        assert line.endswith("INFO     taskflow.test: hello world")

    def test_level_filters_messages(self, capsys):
        setup_logging("WARNING", "text")
        log = get_logger("test")
        log.debug("debug message")
        log.info("info message")
        log.warning("warning message")
        log.error("error message")
        log.critical("critical message")
        out = capsys.readouterr().out
        assert "debug message" not in out
        assert "info message" not in out
        for level in ("warning", "error", "critical"):
            assert f"{level} message" in out

    def test_debug_level_shows_everything(self, capsys):
        setup_logging("DEBUG", "text")
        get_logger("test").debug("debug message")
        assert "DEBUG" in capsys.readouterr().out

    def test_json_format(self, capsys):
        setup_logging("DEBUG", "json")
        get_logger("test").warning("привет")
        record = json.loads(capsys.readouterr().out)
        assert record["level"] == "WARNING"
        assert record["logger"] == "taskflow.test"
        assert record["message"] == "привет"
        assert "time" in record
        assert "exception" not in record

    def test_json_format_includes_exception(self, capsys):
        setup_logging("DEBUG", "json")
        try:
            raise ValueError("boom")
        except ValueError:
            get_logger("test").exception("failed")
        record = json.loads(capsys.readouterr().out)
        assert record["level"] == "ERROR"
        assert "ValueError: boom" in record["exception"]

    def test_repeated_setup_does_not_duplicate_handlers(self):
        setup_logging("INFO")
        logger = setup_logging("DEBUG")
        assert len(logger.handlers) == 1
        assert logger.level == logging.DEBUG
        assert logger.propagate is False

    def test_json_formatter_is_used_only_for_json(self):
        assert isinstance(setup_logging("INFO", "json").handlers[0].formatter, JsonFormatter)
        assert not isinstance(setup_logging("INFO", "text").handlers[0].formatter, JsonFormatter)

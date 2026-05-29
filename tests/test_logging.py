"""Tests for the Aura logging system."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from aura.logging import setup_logging
from aura.logging.config import LogConfig
from aura.logging.context import (
    clear_context,
    get_current_context,
    set_request_id,
    set_user_id,
)
from aura.logging.formatters import JsonFormatter, PlainFormatter
from aura.logging.handlers import DailyRotatingFileHandler
from aura.logging.logger import Log
from aura.logging.sanitizer import Sanitizer


class TestLogConfig:
    """Tests for LogConfig."""

    def test_default_values(self) -> None:
        """Test that LogConfig has correct defaults."""
        config = LogConfig()
        assert config.level == "INFO"
        assert config.dir == "storage/logs"
        assert config.max_lines is None
        assert config.format == "plain"
        assert config.console is True
        assert config.file is True
        assert config.include_request_body is False
        assert config.include_response_body is False
        assert len(config.sanitize_fields) > 0

    def test_env_vars(self, monkeypatch: Any) -> None:
        """Test that LogConfig loads from environment variables."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("LOG_DIR", "/tmp/logs")
        monkeypatch.setenv("LOG_MAX_LINES", "1000")
        monkeypatch.setenv("LOG_FORMAT", "json")
        monkeypatch.setenv("LOG_CONSOLE", "false")
        monkeypatch.setenv("LOG_FILE", "true")

        config = LogConfig()
        assert config.level == "DEBUG"
        assert config.dir == "/tmp/logs"
        assert config.max_lines == 1000
        assert config.format == "json"
        assert config.console is False
        assert config.file is True

    def test_custom_sanitize_fields(self) -> None:
        """Test custom sanitize fields."""
        config = LogConfig(sanitize_fields=["custom_secret"])
        assert "custom_secret" in config.sanitize_fields


class TestSanitizer:
    """Tests for the Sanitizer."""

    def test_sanitize_headers(self) -> None:
        """Test header sanitization."""
        sanitizer = Sanitizer(["password", "token"])
        headers = {"content-type": "application/json", "password": "secret123"}
        sanitized = sanitizer.sanitize_headers(headers)

        assert sanitized["content-type"] == "application/json"
        assert sanitized["password"] == "***REDACTED***"

    def test_sanitize_headers_case_insensitive(self) -> None:
        """Test that header sanitization is case-insensitive."""
        sanitizer = Sanitizer(["password"])
        headers = {"PASSWORD": "secret123", "Password": "secret456"}
        sanitized = sanitizer.sanitize_headers(headers)

        assert sanitized["PASSWORD"] == "***REDACTED***"
        assert sanitized["Password"] == "***REDACTED***"

    def test_sanitize_body_dict(self) -> None:
        """Test body sanitization with dictionary."""
        sanitizer = Sanitizer(["password", "token"])
        body = {"username": "john", "password": "secret123", "token": "abc123"}
        sanitized = sanitizer.sanitize_body(body)

        assert isinstance(sanitized, dict)
        assert sanitized["username"] == "john"
        assert sanitized["password"] == "***REDACTED***"
        assert sanitized["token"] == "***REDACTED***"

    def test_sanitize_body_recursive(self) -> None:
        """Test that body sanitization works recursively."""
        sanitizer = Sanitizer(["password"])
        body = {
            "user": {"password": "secret", "name": "john"},
            "nested": {"deeply": {"password": "hidden"}},
        }
        sanitized = sanitizer.sanitize_body(body)

        assert isinstance(sanitized, dict)
        assert sanitized["user"]["password"] == "***REDACTED***"
        assert sanitized["nested"]["deeply"]["password"] == "***REDACTED***"

    def test_sanitize_body_with_list(self) -> None:
        """Test that body sanitization handles lists."""
        sanitizer = Sanitizer(["password"])
        body = {
            "users": [
                {"name": "john", "password": "secret1"},
                {"name": "jane", "password": "secret2"},
            ]
        }
        sanitized = sanitizer.sanitize_body(body)

        assert sanitized["users"][0]["password"] == "***REDACTED***"
        assert sanitized["users"][1]["password"] == "***REDACTED***"

    def test_sanitize_body_string(self) -> None:
        """Test that string bodies are returned as-is."""
        sanitizer = Sanitizer(["password"])
        body = "plain text body"
        sanitized = sanitizer.sanitize_body(body)

        assert sanitized == body


class TestContext:
    """Tests for context variables."""

    def teardown_method(self) -> None:
        """Clear context after each test."""
        clear_context()

    def test_set_and_get_request_id(self) -> None:
        """Test setting and getting request ID."""
        set_request_id("req-123")
        ctx = get_current_context()
        assert ctx["request_id"] == "req-123"

    def test_set_and_get_user_id(self) -> None:
        """Test setting and getting user ID."""
        set_user_id(42)
        ctx = get_current_context()
        assert ctx["user_id"] == 42

    def test_set_and_get_user_id_string(self) -> None:
        """Test setting user ID as string."""
        set_user_id("user-abc123")
        ctx = get_current_context()
        assert ctx["user_id"] == "user-abc123"

    def test_get_context_empty(self) -> None:
        """Test that empty context returns empty dict."""
        ctx = get_current_context()
        assert ctx == {}

    def test_clear_context(self) -> None:
        """Test clearing context."""
        set_request_id("req-123")
        set_user_id(42)
        clear_context()
        ctx = get_current_context()
        assert ctx == {}

    def test_context_isolation(self) -> None:
        """Test that context modifications don't affect the original."""
        set_request_id("req-123")
        ctx1 = get_current_context()
        ctx1["extra"] = "value"
        ctx2 = get_current_context()
        assert "extra" not in ctx2

    @pytest.mark.asyncio
    async def test_run_with_context_propagates_request_id(self) -> None:
        """Test that run_with_context propagates request_id to coroutine."""
        from aura.logging.context import run_with_context

        captured_context: dict[str, Any] = {}

        async def background_task() -> None:
            nonlocal captured_context
            captured_context = get_current_context()

        context_dict = {"request_id": "bg-req-123"}
        await run_with_context(background_task(), context_dict)

        assert captured_context["request_id"] == "bg-req-123"

    @pytest.mark.asyncio
    async def test_run_with_context_propagates_user_id(self) -> None:
        """Test that run_with_context propagates user_id to coroutine."""
        from aura.logging.context import run_with_context

        captured_context: dict[str, Any] = {}

        async def background_task() -> None:
            nonlocal captured_context
            captured_context = get_current_context()

        context_dict = {"user_id": 999}
        await run_with_context(background_task(), context_dict)

        assert captured_context["user_id"] == 999

    @pytest.mark.asyncio
    async def test_run_with_context_with_both_request_and_user_id(self) -> None:
        """Test that run_with_context propagates both request_id and user_id."""
        from aura.logging.context import run_with_context

        captured_context: dict[str, Any] = {}

        async def background_task() -> None:
            nonlocal captured_context
            captured_context = get_current_context()

        context_dict = {"request_id": "req-123", "user_id": 456}
        await run_with_context(background_task(), context_dict)

        assert captured_context["request_id"] == "req-123"
        assert captured_context["user_id"] == 456


class TestDailyRotatingFileHandler:
    """Tests for DailyRotatingFileHandler."""

    def test_create_log_file(self, tmp_path: Path) -> None:
        """Test that handler creates a log file with correct name."""
        handler = DailyRotatingFileHandler(str(tmp_path))
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        handler.close()

        today = date.today()
        log_file = tmp_path / f"{today.isoformat()}.log"
        assert log_file.exists()
        assert "Test message" in log_file.read_text()

    def test_rotation_by_line_count(self, tmp_path: Path) -> None:
        """Test that handler rotates files when max_lines is reached."""
        handler = DailyRotatingFileHandler(str(tmp_path), max_lines=2)

        for i in range(5):
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg=f"Message {i}",
                args=(),
                exc_info=None,
            )
            handler.emit(record)

        handler.close()

        today = date.today()
        log_file = tmp_path / f"{today.isoformat()}.log"
        rotated_file_1 = tmp_path / f"{today.isoformat()}.1.log"

        assert log_file.exists()
        assert rotated_file_1.exists()

    def test_formatter_applied(self, tmp_path: Path) -> None:
        """Test that formatter is applied to log records."""
        handler = DailyRotatingFileHandler(str(tmp_path))
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        handler.setFormatter(formatter)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        handler.emit(record)
        handler.close()

        today = date.today()
        log_file = tmp_path / f"{today.isoformat()}.log"
        content = log_file.read_text()
        assert "INFO - Test" in content


class TestPlainFormatter:
    """Tests for PlainFormatter."""

    def test_basic_format(self) -> None:
        """Test basic plain text formatting."""
        formatter = PlainFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)

        assert "INFO" in formatted
        assert "Test message" in formatted
        assert "[" in formatted  # timestamp brackets
        assert "]" in formatted

    def test_format_with_request_id(self) -> None:
        """Test formatting includes request_id from context."""
        clear_context()
        set_request_id("req-123")

        formatter = PlainFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)

        assert "[req:req-123]" in formatted

    def test_format_with_extra_fields(self) -> None:
        """Test formatting includes extra fields."""
        clear_context()
        formatter = PlainFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.user_id = 42
        record.endpoint = "/users"
        formatted = formatter.format(record)

        assert "user_id=42" in formatted
        assert "endpoint=/users" in formatted


class TestJsonFormatter:
    """Tests for JsonFormatter."""

    def test_basic_format(self) -> None:
        """Test basic JSON formatting."""
        clear_context()
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)

        data = json.loads(formatted)
        assert data["level"] == "INFO"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_format_with_context(self) -> None:
        """Test JSON formatting includes context."""
        clear_context()
        set_request_id("req-123")
        set_user_id(42)

        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        formatted = formatter.format(record)

        data = json.loads(formatted)
        assert data["request_id"] == "req-123"
        assert data["user_id"] == 42

    def test_format_with_extra_fields(self) -> None:
        """Test JSON formatting includes extra fields."""
        clear_context()
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.ip = "192.168.1.1"
        record.method = "GET"
        formatted = formatter.format(record)

        data = json.loads(formatted)
        assert data["ip"] == "192.168.1.1"
        assert data["method"] == "GET"


class TestLog:
    """Tests for the Log facade."""

    def setup_method(self) -> None:
        """Reset the Log singleton before each test."""
        Log._set_instance(None)
        # Reconfigure aura.app logger for testing
        stdlib_logger = logging.getLogger("aura.app")
        stdlib_logger.handlers.clear()
        stdlib_logger.setLevel(logging.DEBUG)

    def teardown_method(self) -> None:
        """Clear context after each test."""
        clear_context()

    def test_log_info(self, caplog: Any) -> None:
        """Test Log.info works before setup."""
        with caplog.at_level(logging.INFO):
            Log.info("Test message")
        assert "Test message" in caplog.text

    def test_log_error(self, caplog: Any) -> None:
        """Test Log.error works."""
        with caplog.at_level(logging.ERROR):
            Log.error("Error message")
        assert "Error message" in caplog.text

    def test_log_debug(self, caplog: Any) -> None:
        """Test Log.debug works."""
        with caplog.at_level(logging.DEBUG):
            Log.debug("Debug message")
        assert "Debug message" in caplog.text

    def test_log_warning(self, caplog: Any) -> None:
        """Test Log.warning works."""
        with caplog.at_level(logging.WARNING):
            Log.warning("Warning message")
        assert "Warning message" in caplog.text

    def test_log_critical(self, caplog: Any) -> None:
        """Test Log.critical works."""
        with caplog.at_level(logging.CRITICAL):
            Log.critical("Critical message")
        assert "Critical message" in caplog.text

    def test_log_with_extra_fields(self, caplog: Any) -> None:
        """Test Log includes extra keyword arguments."""
        with caplog.at_level(logging.INFO):
            Log.info("Test", user_id=42, endpoint="/users")
        assert "Test" in caplog.text

    def test_log_with_exception(self, caplog: Any) -> None:
        """Test Log.error includes exception info."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            with caplog.at_level(logging.ERROR):
                Log.error("An error occurred", exc=e)

        assert "An error occurred" in caplog.text
        assert "ValueError" in caplog.text

    def test_log_exception_method(self, caplog: Any) -> None:
        """Test Log.exception includes exception info."""
        try:
            raise RuntimeError("Test runtime error")
        except RuntimeError as e:
            with caplog.at_level(logging.ERROR):
                Log.exception("Error occurred", e)

        assert "Error occurred" in caplog.text


class TestSetupLogging:
    """Tests for setup_logging function."""

    def teardown_method(self) -> None:
        """Reset the Log singleton and stdlib logger after each test."""
        Log._set_instance(None)
        # Reset stdlib logger to default state
        stdlib_logger = logging.getLogger("aura.app")
        stdlib_logger.handlers.clear()
        stdlib_logger.setLevel(logging.WARNING)

    def test_setup_logging_console_plain(self, tmp_path: Path) -> None:
        """Test setup_logging with console and plain format."""
        config = LogConfig(
            level="INFO", format="plain", console=True, file=False
        )
        setup_logging(config)

        Log.info("Test message")

    def test_setup_logging_file_plain(self, tmp_path: Path) -> None:
        """Test setup_logging with file output and plain format."""
        config = LogConfig(
            level="INFO",
            format="plain",
            dir=str(tmp_path),
            console=False,
            file=True,
        )
        setup_logging(config)

        Log.info("Test message")

        today = date.today()
        log_file = tmp_path / f"{today.isoformat()}.log"
        assert log_file.exists()

    def test_setup_logging_json(self, tmp_path: Path) -> None:
        """Test setup_logging with JSON format."""
        config = LogConfig(
            level="DEBUG",
            format="json",
            dir=str(tmp_path),
            console=False,
            file=True,
        )
        setup_logging(config)

        Log.info("Test message")

        today = date.today()
        log_file = tmp_path / f"{today.isoformat()}.log"
        content = log_file.read_text()
        data = json.loads(content.strip())
        assert data["message"] == "Test message"

    def test_setup_logging_both_handlers(self, tmp_path: Path) -> None:
        """Test setup_logging with both console and file handlers."""
        config = LogConfig(
            level="INFO",
            format="plain",
            dir=str(tmp_path),
            console=True,
            file=True,
        )
        setup_logging(config)

        Log.info("Test message")

        today = date.today()
        log_file = tmp_path / f"{today.isoformat()}.log"
        assert log_file.exists()


class TestRequestLogInterceptor:
    """Tests for RequestLogInterceptor."""

    def test_interceptor_initialization(self) -> None:
        """Test that interceptor can be initialized."""
        from aura.logging.interceptor import RequestLogInterceptor

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            pass

        interceptor = RequestLogInterceptor(dummy_app)
        assert interceptor.app is dummy_app
        assert interceptor.extract_request_id_header == "x-request-id"
        assert interceptor.log_headers is False

    def test_interceptor_custom_header(self) -> None:
        """Test that interceptor respects custom request_id header."""
        from aura.logging.interceptor import RequestLogInterceptor

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            pass

        interceptor = RequestLogInterceptor(
            dummy_app, extract_request_id_header="X-Correlation-ID"
        )
        assert interceptor.extract_request_id_header == "x-correlation-id"

    @pytest.mark.asyncio
    async def test_interceptor_non_http_request(self) -> None:
        """Test that non-HTTP requests pass through untouched."""
        from aura.logging.interceptor import RequestLogInterceptor

        clear_context()
        app_called = False

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            nonlocal app_called
            app_called = True

        interceptor = RequestLogInterceptor(dummy_app)

        scope = {"type": "lifespan"}

        async def mock_receive() -> Any:
            return {}

        async def mock_send(message: Any) -> None:
            pass

        await interceptor(scope, mock_receive, mock_send)
        assert app_called

    @pytest.mark.asyncio
    async def test_interceptor_http_with_header(self) -> None:
        """Test that HTTP request with X-Request-ID header sets context."""
        from aura.logging.interceptor import RequestLogInterceptor

        clear_context()
        request_id_in_context: str | None = None

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            nonlocal request_id_in_context
            from aura.logging.context import get_current_context
            context = get_current_context()
            request_id_in_context = context.get("request_id")

        interceptor = RequestLogInterceptor(dummy_app)

        scope = {
            "type": "http",
            "headers": [
                (b"x-request-id", b"test-req-123"),
            ],
        }

        async def mock_receive() -> Any:
            return {}

        async def mock_send(message: Any) -> None:
            pass

        await interceptor(scope, mock_receive, mock_send)
        assert request_id_in_context == "test-req-123"

    @pytest.mark.asyncio
    async def test_interceptor_http_without_header_generates_uuid(self) -> None:
        """Test that HTTP request without X-Request-ID generates UUID."""
        from aura.logging.interceptor import RequestLogInterceptor

        clear_context()
        request_id_in_context: str | None = None

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            nonlocal request_id_in_context
            from aura.logging.context import get_current_context
            context = get_current_context()
            request_id_in_context = context.get("request_id")

        interceptor = RequestLogInterceptor(dummy_app, generate_request_id=True)

        scope = {
            "type": "http",
            "headers": [],
        }

        async def mock_receive() -> Any:
            return {}

        async def mock_send(message: Any) -> None:
            pass

        await interceptor(scope, mock_receive, mock_send)
        assert request_id_in_context is not None
        assert len(request_id_in_context) > 0

    @pytest.mark.asyncio
    async def test_interceptor_context_cleared_after_request(self) -> None:
        """Test that context is cleared in finally block after request."""
        from aura.logging.interceptor import RequestLogInterceptor

        clear_context()

        async def dummy_app(scope: Any, receive: Any, send: Any) -> None:
            from aura.logging.context import get_current_context
            context = get_current_context()
            assert "request_id" in context  # Context is set during request

        interceptor = RequestLogInterceptor(dummy_app)

        scope = {
            "type": "http",
            "headers": [
                (b"x-request-id", b"test-req-456"),
            ],
        }

        async def mock_receive() -> Any:
            return {}

        async def mock_send(message: Any) -> None:
            pass

        await interceptor(scope, mock_receive, mock_send)
        # After request, context should be cleared
        from aura.logging.context import get_current_context
        assert get_current_context() == {}

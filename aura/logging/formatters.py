"""Logging formatters for different output formats."""

from __future__ import annotations

import json
import logging
from typing import Any

from aura.logging.context import get_current_context
from aura.logging.sanitizer import Sanitizer


class PlainFormatter(logging.Formatter):
    """Plain text formatter with context support."""

    def __init__(self, sanitizer: Sanitizer | None = None) -> None:
        """Initialize the plain formatter.

        Args:
            sanitizer: Optional sanitizer for sensitive fields.
        """
        super().__init__()
        self.sanitizer = sanitizer

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as plain text.

        Args:
            record: The log record to format.

        Returns:
            Formatted log record string.
        """
        # Get context
        context = get_current_context()

        # Build timestamp
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        # Build context string
        context_str = ""
        if context.get("request_id"):
            context_str += f" [req:{context['request_id']}]"
        if context.get("user_id"):
            context_str += f" [user:{context['user_id']}]"

        # Add extra fields from record
        extras = []
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "taskName",
            ):
                if isinstance(value, dict) and self.sanitizer:
                    value = self.sanitizer.sanitize_body(value)
                extras.append(f"{key}={value}")

        extras_str = " " + " ".join(extras) if extras else ""

        line = (
            f"[{timestamp}] {record.levelname:<8} {record.name}: "
            f"{record.getMessage()}{context_str}{extras_str}"
        )

        # Append exception traceback and stack info when present
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            line = f"{line}\n{record.exc_text}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"

        return line


class JsonFormatter(logging.Formatter):
    """JSON formatter with context and structured field support."""

    def __init__(self, sanitizer: Sanitizer | None = None) -> None:
        """Initialize the JSON formatter.

        Args:
            sanitizer: Optional sanitizer for sensitive fields.
        """
        super().__init__()
        self.sanitizer = sanitizer

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: The log record to format.

        Returns:
            JSON-formatted log record.
        """
        # Get context
        context = get_current_context()

        # Build base log dict
        log_dict: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add context
        log_dict.update(context)

        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "taskName",
            ):
                if isinstance(value, dict) and self.sanitizer:
                    log_dict[key] = self.sanitizer.sanitize_body(value)
                else:
                    log_dict[key] = value

        # Append exception traceback and stack info when present
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_dict["exception"] = record.exc_text
        if record.stack_info:
            log_dict["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_dict, default=str)

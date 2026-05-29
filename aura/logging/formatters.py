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
            ):
                extras.append(f"{key}={value}")

        extras_str = " " + " ".join(extras) if extras else ""

        return (
            f"[{timestamp}] {record.levelname:<8} {record.name}: "
            f"{record.getMessage()}{context_str}{extras_str}"
        )


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
            ):
                if isinstance(value, dict) and self.sanitizer:
                    log_dict[key] = self.sanitizer.sanitize_body(value)
                else:
                    log_dict[key] = value

        return json.dumps(log_dict)

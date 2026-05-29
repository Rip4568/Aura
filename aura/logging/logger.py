"""Core logger implementation."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from aura.logging.context import get_current_context


class AuraLogger:
    """Internal worker logger for Aura's logging system.

    This class wraps the stdlib logging.Logger and handles context
    propagation and level mapping. Do not use directly — use Log facade instead.
    """

    def __init__(self, stdlib_logger: logging.Logger) -> None:
        """Initialize the AuraLogger with a stdlib logger.

        Args:
            stdlib_logger: The underlying stdlib logging.Logger instance.
        """
        self._logger = stdlib_logger

    def log(
        self,
        level: str,
        msg: str,
        *,
        exc: BaseException | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Log a message at the specified level.

        Args:
            level: Log level as string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
            msg: The log message.
            exc: Optional exception to include in the log.
            extra: Optional dictionary of extra fields to include in the log.
        """
        # Merge extra with context variables
        merged_extra: dict[str, Any] = {}
        ctx = get_current_context()
        if ctx:
            merged_extra.update(ctx)
        if extra:
            merged_extra.update(extra)

        # Map level string to logging constant
        level_int = getattr(logging, level.upper(), logging.INFO)

        # Log with merged extra fields
        self._logger.log(
            level_int,
            msg,
            extra=merged_extra,
            exc_info=exc,
        )


class Log:
    """Facade for static logging access.

    Use this class directly for logging throughout the application.
    No instantiation needed.

    Example::

        Log.info("User created", user_id=42)
        Log.error("Database error", exc=exception, query="SELECT ...")
        Log.debug("Request started", method="GET", path="/users")
    """

    _instance: ClassVar[AuraLogger | None] = None

    @classmethod
    def _set_instance(cls, instance: AuraLogger) -> None:
        """Set the AuraLogger instance (called by setup_logging).

        Args:
            instance: The AuraLogger instance to use for logging.
        """
        cls._instance = instance

    @classmethod
    def _get_logger(cls) -> AuraLogger:
        """Get the current logger instance, creating a fallback if needed.

        Returns:
            The current AuraLogger instance.
        """
        if cls._instance is None:
            # Fallback to stdlib logging before setup
            stdlib = logging.getLogger("aura.app")
            cls._instance = AuraLogger(stdlib)
        return cls._instance

    @classmethod
    def debug(
        cls, msg: str, *, exc: BaseException | None = None, **extra: Any
    ) -> None:
        """Log a debug message.

        Args:
            msg: The log message.
            exc: Optional exception to include.
            **extra: Additional fields to include in the log.
        """
        cls._get_logger().log("DEBUG", msg, exc=exc, extra=extra)

    @classmethod
    def info(
        cls, msg: str, *, exc: BaseException | None = None, **extra: Any
    ) -> None:
        """Log an info message.

        Args:
            msg: The log message.
            exc: Optional exception to include.
            **extra: Additional fields to include in the log.
        """
        cls._get_logger().log("INFO", msg, exc=exc, extra=extra)

    @classmethod
    def warning(
        cls, msg: str, *, exc: BaseException | None = None, **extra: Any
    ) -> None:
        """Log a warning message.

        Args:
            msg: The log message.
            exc: Optional exception to include.
            **extra: Additional fields to include in the log.
        """
        cls._get_logger().log("WARNING", msg, exc=exc, extra=extra)

    @classmethod
    def error(
        cls, msg: str, *, exc: BaseException | None = None, **extra: Any
    ) -> None:
        """Log an error message.

        Args:
            msg: The log message.
            exc: Optional exception to include.
            **extra: Additional fields to include in the log.
        """
        cls._get_logger().log("ERROR", msg, exc=exc, extra=extra)

    @classmethod
    def critical(
        cls, msg: str, *, exc: BaseException | None = None, **extra: Any
    ) -> None:
        """Log a critical message.

        Args:
            msg: The log message.
            exc: Optional exception to include.
            **extra: Additional fields to include in the log.
        """
        cls._get_logger().log("CRITICAL", msg, exc=exc, extra=extra)

    @classmethod
    def exception(cls, msg: str, exc: BaseException, **extra: Any) -> None:
        """Log an exception at ERROR level.

        Args:
            msg: The log message.
            exc: The exception to log.
            **extra: Additional fields to include in the log.
        """
        cls._get_logger().log("ERROR", msg, exc=exc, extra=extra)

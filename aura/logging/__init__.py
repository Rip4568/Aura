"""Aura logging system — structured, async-first logging with context propagation."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

from aura.logging.config import LogConfig
from aura.logging.context import (
    clear_context,
    get_current_context,
    set_request_id,
    set_user_id,
)
from aura.logging.formatters import JsonFormatter, PlainFormatter
from aura.logging.handlers import DailyRotatingFileHandler
from aura.logging.interceptor import RequestLogInterceptor
from aura.logging.logger import AuraLogger, Log
from aura.logging.sanitizer import Sanitizer

if TYPE_CHECKING:
    pass

__all__ = [
    "Log",
    "LogConfig",
    "RequestLogInterceptor",
    "set_request_id",
    "set_user_id",
    "get_current_context",
    "clear_context",
    "AuraLogger",
    "PlainFormatter",
    "JsonFormatter",
    "DailyRotatingFileHandler",
    "Sanitizer",
]


def setup_logging(config: LogConfig) -> None:
    """Initialize the Aura logging system with the provided configuration.

    This function is called during application startup in Aura._on_startup.
    It configures the stdlib logging system, creates handlers, and registers
    the AuraLogger singleton for use throughout the application.

    Args:
        config: LogConfig instance with level, format, handlers, etc.

    Example::

        from aura.logging import setup_logging, LogConfig

        config = LogConfig(level="DEBUG", format="json")
        setup_logging(config)
        Log.info("Application started")
    """
    # 1. Configure the "aura" parent logger so all child loggers (aura.app,
    #    aura.access, etc.) inherit handlers and level via propagation.
    stdlib_logger = logging.getLogger("aura")
    stdlib_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    for _h in stdlib_logger.handlers[:]:
        _h.close()
    stdlib_logger.handlers.clear()

    # 2. Choose formatter based on config
    if config.format == "json":
        formatter: logging.Formatter = JsonFormatter()
    else:
        formatter = PlainFormatter()

    # 3. Add console handler if enabled
    if config.console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        stdlib_logger.addHandler(console_handler)

    # 4. Add file handler if enabled
    if config.file:
        file_handler = DailyRotatingFileHandler(
            log_dir=config.dir,
            max_lines=config.max_lines,
        )
        file_handler.setFormatter(formatter)
        stdlib_logger.addHandler(file_handler)

    # 5. Create and register AuraLogger singleton
    aura_logger = AuraLogger(stdlib_logger)
    Log._set_instance(aura_logger)

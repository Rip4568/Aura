"""Configuration for the logging system."""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aura.logging.constants import DEFAULT_SENSITIVE_FIELDS


class LogConfig(BaseSettings):
    """Configuration for Aura's logging system.

    Attributes:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        dir: Directory path where log files are stored.
        max_lines: Maximum number of lines per log file before rotation.
                   If None, no rotation by line count.
        format: Output format - "plain" or "json".
        console: Enable console (stdout) output.
        file: Enable file output.
        sanitize_fields: List of field names to redact from logs.
        include_request_body: Include request body in logs (use cautiously).
        include_response_body: Include response body in logs (use cautiously).
    """

    model_config = SettingsConfigDict(env_prefix="LOG_", extra="ignore")

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    dir: str = "storage/logs"
    max_lines: int | None = None
    format: Literal["plain", "json"] = "plain"
    console: bool = True
    file: bool = True
    sanitize_fields: list[str] = Field(default_factory=lambda: list(DEFAULT_SENSITIVE_FIELDS))
    include_request_body: bool = False
    include_response_body: bool = False

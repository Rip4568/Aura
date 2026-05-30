"""Constants for the logging system."""

from __future__ import annotations

DEFAULT_SENSITIVE_FIELDS = [
    "password",
    "passwd",
    "pwd",
    "token",
    "apikey",
    "api_key",
    "api-key",
    "secret",
    "authorization",
    "auth",
    "bearer",
    "x-api-key",
    "x-auth-token",
    "credit_card",
    "card_number",
    "cvv",
    "ssn",
]

LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

REDACTED_VALUE = "***REDACTED***"

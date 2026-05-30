"""Data sanitizer for sensitive fields in logs."""

from __future__ import annotations

from typing import Any

from aura.logging.constants import REDACTED_VALUE


class Sanitizer:
    """Sanitizer for sensitive data in logs.

    Redacts passwords, tokens, and other sensitive fields from log output.
    """

    def __init__(self, sensitive_fields: list[str]) -> None:
        """Initialize the sanitizer with a list of sensitive field names.

        Args:
            sensitive_fields: List of field names to redact (case-insensitive).
        """
        self.sensitive_fields = {field.lower() for field in sensitive_fields}

    def sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Sanitize HTTP headers, masking sensitive ones.

        Args:
            headers: Dictionary of header names and values.

        Returns:
            Dictionary with sensitive headers redacted.
        """
        result = {}
        for key, value in headers.items():
            if key.lower() in self.sensitive_fields:
                result[key] = REDACTED_VALUE
            else:
                result[key] = value
        return result

    def sanitize_body(self, body: dict[str, Any] | str) -> dict[str, Any] | str:
        """Sanitize request/response body, recursively redacting sensitive fields.

        Args:
            body: Dictionary or string body to sanitize.

        Returns:
            Sanitized body (dict or str, same as input).
        """
        if isinstance(body, str):
            return body

        if not isinstance(body, dict):
            return body

        return self._sanitize_dict(body)

    def _sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize a dictionary.

        Args:
            data: Dictionary to sanitize.

        Returns:
            Sanitized dictionary.
        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in self.sensitive_fields:
                result[key] = REDACTED_VALUE
            elif isinstance(value, dict):
                result[key] = self._sanitize_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self._sanitize_dict(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

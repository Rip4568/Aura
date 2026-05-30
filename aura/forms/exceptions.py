"""Form-related exceptions for the Aura Forms module."""

from __future__ import annotations

from typing import Any


class FieldValidationError(Exception):
    """Raised by a Field when a single-field validation fails.

    Attributes:
        message: Human-readable error description.
        messages: List of error messages (allows multiple errors per field).
        code: Optional machine-readable error code.
    """

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.messages: list[str] = [message]
        self.code = code


class FormValidationError(Exception):
    """Raised when form-level validation fails.

    When raised inside an HTTP handler, the router converts it to a 422
    Unprocessable Entity response automatically.

    Response structure::

        {
          "error": {
            "status": 422,
            "message": "Validation failed",
            "code": "FORM_VALIDATION_ERROR",
            "detail": {"campo": ["mensagem"], "__all__": ["erro global"]}
          }
        }

    Attributes:
        message: Human-readable summary.
        code: Machine-readable error code (``"FORM_VALIDATION_ERROR"``).
        errors: Dict mapping field names to lists of error messages.
                Use ``"__all__"`` key for non-field errors.
    """

    def __init__(
        self,
        errors: dict[str, list[str]],
        *,
        message: str = "Validation failed",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = "FORM_VALIDATION_ERROR"
        self.errors: dict[str, list[str]] = errors

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the standard Aura error response shape."""
        return {
            "error": {
                "status": 422,
                "message": self.message,
                "code": self.code,
                "detail": self.errors,
            }
        }

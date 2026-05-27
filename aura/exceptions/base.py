"""Base exception class for the Aura framework."""

from __future__ import annotations

from typing import Any


class AuraException(Exception):
    """
    Root exception for all Aura-specific errors.

    All framework-level exceptions inherit from this class so that
    application code can catch everything Aura raises with a single
    ``except AuraException`` clause.

    Attributes:
        message: Human-readable description of the error.
        code: Optional machine-readable error code (e.g. ``"USER_NOT_FOUND"``).
        detail: Arbitrary additional context attached to the error.
    """

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        *,
        code: str | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.detail = detail

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"code={self.code!r}, "
            f"detail={self.detail!r})"
        )

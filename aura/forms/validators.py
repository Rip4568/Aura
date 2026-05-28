"""Pure validator callables for Aura Forms fields."""

from __future__ import annotations

import re
from collections.abc import Callable

from aura.forms.exceptions import FieldValidationError

# ---------------------------------------------------------------------------
# Length validators
# ---------------------------------------------------------------------------


def validate_min_length(min_length: int) -> Callable[[str | None], None]:
    """Return a validator that enforces a minimum string length."""

    def _validator(value: str | None) -> None:
        if value is None:
            return
        if len(value) < min_length:
            raise FieldValidationError(
                f"Este campo deve ter no mínimo {min_length} caractere(s).",
                code="min_length",
            )

    return _validator


def validate_max_length(max_length: int) -> Callable[[str | None], None]:
    """Return a validator that enforces a maximum string length."""

    def _validator(value: str | None) -> None:
        if value is None:
            return
        if len(value) > max_length:
            raise FieldValidationError(
                f"Este campo deve ter no máximo {max_length} caractere(s).",
                code="max_length",
            )

    return _validator


# ---------------------------------------------------------------------------
# Numeric validators
# ---------------------------------------------------------------------------


def validate_min_value(
    min_value: int | float,
) -> Callable[[int | float | None], None]:
    """Return a validator that enforces a minimum numeric value."""

    def _validator(value: int | float | None) -> None:
        if value is None:
            return
        if value < min_value:
            raise FieldValidationError(
                f"Este campo deve ser maior ou igual a {min_value}.",
                code="min_value",
            )

    return _validator


def validate_max_value(
    max_value: int | float,
) -> Callable[[int | float | None], None]:
    """Return a validator that enforces a maximum numeric value."""

    def _validator(value: int | float | None) -> None:
        if value is None:
            return
        if value > max_value:
            raise FieldValidationError(
                f"Este campo deve ser menor ou igual a {max_value}.",
                code="max_value",
            )

    return _validator


# ---------------------------------------------------------------------------
# Format validators
# ---------------------------------------------------------------------------

# Simple RFC 5322-inspired regex (covers the vast majority of real addresses)
_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

_URL_REGEX = re.compile(r"^https?://\S+$")

_SLUG_REGEX = re.compile(r"^[a-z0-9_\-]+$")


def validate_email(value: str | None) -> None:
    """Validate that *value* looks like a valid e-mail address."""
    if value is None:
        return
    if not _EMAIL_REGEX.match(value):
        raise FieldValidationError(
            "Informe um endereço de e-mail válido.",
            code="invalid_email",
        )


def validate_url(value: str | None) -> None:
    """Validate that *value* starts with ``http://`` or ``https://``."""
    if value is None:
        return
    if not _URL_REGEX.match(value):
        raise FieldValidationError(
            "Informe uma URL válida começando com http:// ou https://.",
            code="invalid_url",
        )


def validate_slug(value: str | None) -> None:
    """Validate that *value* contains only ``[a-z0-9_-]``."""
    if value is None:
        return
    if not _SLUG_REGEX.match(value):
        raise FieldValidationError(
            "Informe um slug válido (apenas letras minúsculas, números, hífens e underscores).",
            code="invalid_slug",
        )


def validate_regex(
    pattern: str,
    message: str | None = None,
) -> Callable[[str | None], None]:
    """Return a validator that matches *value* against *pattern*."""
    compiled = re.compile(pattern)
    error_message = message or f"O valor não corresponde ao padrão esperado ({pattern})."

    def _validator(value: str | None) -> None:
        if value is None:
            return
        if not compiled.search(value):
            raise FieldValidationError(error_message, code="invalid_regex")

    return _validator

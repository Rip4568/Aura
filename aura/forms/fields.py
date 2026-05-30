"""Field classes for Aura Forms.

Every field follows the same contract:
* ``run(raw)``        — coerce raw input then validate; returns the typed value.
* ``to_python(raw)``  — coerce raw → Python type (returns None when empty & not required).
* ``validate(value)`` — run registered validators; raises FieldValidationError on failure.
"""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Generic, TypeVar, cast

from aura.forms.exceptions import FieldValidationError
from aura.forms.validators import (
    validate_email,
    validate_max_length,
    validate_max_value,
    validate_min_length,
    validate_min_value,
    validate_slug,
    validate_url,
)

T = TypeVar("T")

# ---------------------------------------------------------------------------
# Base Field
# ---------------------------------------------------------------------------


class Field(ABC, Generic[T]):
    """Abstract base for all Aura form fields.

    Attributes:
        required: Whether a non-empty value is mandatory (default ``True``).
        validators: Additional validator callables added at construction time.
        label: Human-readable label (optional, used by template rendering).
        help_text: Descriptive text shown near the field in templates.
        default: Value to use when the raw input is absent/empty and the field
                 is not required.  Defaults to ``None``.
        default_widget_class: Name hint for the default HTML widget.
    """

    default_widget_class: str = "text"

    def __init__(
        self,
        *,
        required: bool = True,
        validators: list[Callable[[Any], None]] | None = None,
        label: str | None = None,
        help_text: str | None = None,
        default: Any = None,
    ) -> None:
        self.required = required
        self.validators: list[Callable[[Any], None]] = list(validators or [])
        self.label = label
        self.help_text = help_text
        self.default = default

    # ------------------------------------------------------------------
    # Coercion — override in subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    def to_python(self, raw: Any) -> T | None:
        """Convert *raw* input to a Python value.

        Must return ``None`` (or the field default) when *raw* is ``None``
        or an empty string and ``required`` is ``False``.
        """

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, value: T | None) -> None:
        """Run all registered validators against *value*.

        Raises:
            FieldValidationError: on the first failing validator, or when
                *value* is ``None`` / empty and the field is required.
        """
        if value is None or (isinstance(value, str) and not value):
            if self.required:
                raise FieldValidationError(
                    "Este campo é obrigatório.", code="required"
                )
            return
        for validator in self.validators:
            validator(value)

    # ------------------------------------------------------------------
    # Combined run
    # ------------------------------------------------------------------

    def run(self, raw: Any) -> T | None:
        """Coerce then validate *raw*, returning the typed value."""
        value = self.to_python(raw)
        self.validate(value)
        return value

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_empty(self, raw: Any) -> bool:
        """Return True when *raw* counts as an absent / empty value."""
        if raw is None:
            return True
        if isinstance(raw, str) and not raw.strip():
            return True
        return False


# ---------------------------------------------------------------------------
# Scalar fields
# ---------------------------------------------------------------------------


class CharField(Field[str]):
    """Single-line text field."""

    default_widget_class = "text"

    def __init__(
        self,
        *,
        max_length: int | None = None,
        min_length: int | None = None,
        strip: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.max_length = max_length
        self.min_length = min_length
        self.strip = strip
        if min_length is not None:
            self.validators.insert(0, validate_min_length(min_length))
        if max_length is not None:
            self.validators.append(validate_max_length(max_length))

    def to_python(self, raw: Any) -> str | None:
        if self._is_empty(raw):
            return cast("str | None", self.default)
        value = str(raw)
        return value.strip() if self.strip else value


class TextField(CharField):
    """Multi-line text field — semantically equivalent to CharField."""

    default_widget_class = "textarea"


class IntField(Field[int]):
    """Integer field."""

    default_widget_class = "number"

    def __init__(
        self,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
        if min_value is not None:
            self.validators.insert(0, validate_min_value(min_value))
        if max_value is not None:
            self.validators.append(validate_max_value(max_value))

    def to_python(self, raw: Any) -> int | None:
        if self._is_empty(raw):
            return cast("int | None", self.default)
        try:
            return int(raw)
        except (ValueError, TypeError) as exc:
            raise FieldValidationError(
                "Informe um número inteiro válido.", code="invalid_int"
            ) from exc


class FloatField(Field[float]):
    """Float field."""

    default_widget_class = "number"

    def __init__(
        self,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
        if min_value is not None:
            self.validators.insert(0, validate_min_value(min_value))
        if max_value is not None:
            self.validators.append(validate_max_value(max_value))

    def to_python(self, raw: Any) -> float | None:
        if self._is_empty(raw):
            return cast("float | None", self.default)
        try:
            return float(raw)
        except (ValueError, TypeError) as exc:
            raise FieldValidationError(
                "Informe um número decimal válido.", code="invalid_float"
            ) from exc


class DecimalField(Field[Decimal]):
    """Decimal field with precision control."""

    default_widget_class = "number"

    def __init__(
        self,
        *,
        max_digits: int | None = None,
        decimal_places: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.max_digits = max_digits
        self.decimal_places = decimal_places

    def to_python(self, raw: Any) -> Decimal | None:
        if self._is_empty(raw):
            return cast("Decimal | None", self.default)
        try:
            value = Decimal(str(raw))
            if self.decimal_places is not None:
                quantize_str = "1." + "0" * self.decimal_places
                value = value.quantize(Decimal(quantize_str))
            return value
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise FieldValidationError(
                "Informe um valor decimal válido.", code="invalid_decimal"
            ) from exc

    def validate(self, value: Decimal | None) -> None:
        super().validate(value)
        if value is None:
            return
        if self.max_digits is not None:
            digits = len(value.as_tuple().digits)
            if digits > self.max_digits:
                raise FieldValidationError(
                    f"Garanta que não haja mais de {self.max_digits} dígito(s) no total.",
                    code="max_digits",
                )


class BoolField(Field[bool]):
    """Boolean field.

    A missing field in raw_data (``raw=None``) with ``required=False`` returns
    ``False`` rather than ``None``, matching HTML checkbox semantics.
    """

    default_widget_class = "checkbox"

    _TRUE_VALUES = {"true", "1", "on", "yes"}
    _FALSE_VALUES = {"false", "0", "off", "no"}

    def to_python(self, raw: Any) -> bool:
        if raw is None:
            # Absent checkbox → False (not None)
            return False
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            lower = raw.lower()
            if lower in self._TRUE_VALUES:
                return True
            if lower in self._FALSE_VALUES:
                return False
        try:
            return bool(int(str(raw)))
        except (ValueError, TypeError) as exc:
            raise FieldValidationError(
                "Informe um valor booleano válido (true/false, 1/0).",
                code="invalid_bool",
            ) from exc

    def validate(self, value: bool | None) -> None:  # noqa: FBT001
        # BoolField never has a "missing" value — absent raw → False
        if self.required and not value:
            raise FieldValidationError(
                "Este campo é obrigatório.", code="required"
            )
        for validator in self.validators:
            validator(value)


class EmailField(CharField):
    """CharField that also validates e-mail format."""

    default_widget_class = "email"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.validators.append(validate_email)


class URLField(CharField):
    """CharField that also validates URL format."""

    default_widget_class = "url"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.validators.append(validate_url)


class SlugField(CharField):
    """CharField that also validates slug format ``[a-z0-9_-]``."""

    default_widget_class = "text"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.validators.append(validate_slug)


# ---------------------------------------------------------------------------
# Date / time fields
# ---------------------------------------------------------------------------


class DateField(Field[date]):
    """Date field — parses ISO strings using *input_formats*."""

    default_widget_class = "date"
    default_input_formats = ["%Y-%m-%d"]

    def __init__(
        self,
        *,
        input_formats: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.input_formats = input_formats or self.default_input_formats

    def to_python(self, raw: Any) -> date | None:
        if self._is_empty(raw):
            return cast("date | None", self.default)
        if isinstance(raw, date) and not isinstance(raw, datetime):
            return raw
        if isinstance(raw, datetime):
            return raw.date()
        for fmt in self.input_formats:
            try:
                return datetime.strptime(str(raw), fmt).date()
            except ValueError:
                continue
        raise FieldValidationError(
            f"Informe uma data válida. Formatos aceitos: {', '.join(self.input_formats)}.",
            code="invalid_date",
        )


class DateTimeField(Field[datetime]):
    """Datetime field — parses ISO strings using *input_formats*."""

    default_widget_class = "datetime-local"
    default_input_formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]

    def __init__(
        self,
        *,
        input_formats: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.input_formats = input_formats or self.default_input_formats

    def to_python(self, raw: Any) -> datetime | None:
        if self._is_empty(raw):
            return cast("datetime | None", self.default)
        if isinstance(raw, datetime):
            return raw
        for fmt in self.input_formats:
            try:
                return datetime.strptime(str(raw), fmt)
            except ValueError:
                continue
        raise FieldValidationError(
            f"Informe uma data/hora válida. Formatos aceitos: {', '.join(self.input_formats)}.",
            code="invalid_datetime",
        )


class TimeField(Field[time]):
    """Time field — parses strings using *input_formats*."""

    default_widget_class = "time"
    default_input_formats = ["%H:%M:%S", "%H:%M"]

    def __init__(
        self,
        *,
        input_formats: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.input_formats = input_formats or self.default_input_formats

    def to_python(self, raw: Any) -> time | None:
        if self._is_empty(raw):
            return cast("time | None", self.default)
        if isinstance(raw, time):
            return raw
        for fmt in self.input_formats:
            try:
                return datetime.strptime(str(raw), fmt).time()
            except ValueError:
                continue
        raise FieldValidationError(
            f"Informe um horário válido. Formatos aceitos: {', '.join(self.input_formats)}.",
            code="invalid_time",
        )


# ---------------------------------------------------------------------------
# Special fields
# ---------------------------------------------------------------------------


class UUIDField(Field[uuid.UUID]):
    """Field that accepts UUID strings and returns ``uuid.UUID`` instances."""

    default_widget_class = "text"

    def to_python(self, raw: Any) -> uuid.UUID | None:
        if self._is_empty(raw):
            return cast("uuid.UUID | None", self.default)
        if isinstance(raw, uuid.UUID):
            return raw
        try:
            return uuid.UUID(str(raw))
        except (ValueError, AttributeError) as exc:
            raise FieldValidationError(
                "Informe um UUID válido.", code="invalid_uuid"
            ) from exc


class JSONField(Field[Any]):
    """Field that accepts a JSON string or a Python dict/list."""

    default_widget_class = "textarea"

    def to_python(self, raw: Any) -> Any:
        if self._is_empty(raw):
            return self.default
        if isinstance(raw, (dict, list)):
            return raw
        try:
            return json.loads(str(raw))
        except (json.JSONDecodeError, TypeError) as exc:
            raise FieldValidationError(
                "Informe um JSON válido.", code="invalid_json"
            ) from exc


# ---------------------------------------------------------------------------
# Choice fields
# ---------------------------------------------------------------------------


class ChoiceField(Field[str]):
    """Field that validates the value against a fixed set of choices."""

    default_widget_class = "select"

    def __init__(
        self,
        choices: list[str] | list[tuple[str, str]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        # Normalise to list[str] of valid *values*
        self._choices = choices
        self._valid_values: set[str] = set()
        for choice in choices:
            if isinstance(choice, tuple):
                self._valid_values.add(choice[0])
            else:
                self._valid_values.add(choice)

    def to_python(self, raw: Any) -> str | None:
        if self._is_empty(raw):
            return cast("str | None", self.default)
        return str(raw)

    def validate(self, value: str | None) -> None:
        super().validate(value)
        if value is None:
            return
        if value not in self._valid_values:
            raise FieldValidationError(
                f"Selecione uma opção válida. '{value}' não é uma das escolhas disponíveis.",
                code="invalid_choice",
            )


class MultipleChoiceField(Field[list[str]]):
    """Field that accepts a list of values, all within the allowed choices."""

    default_widget_class = "select-multiple"

    def __init__(
        self,
        choices: list[str] | list[tuple[str, str]],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._choices = choices
        self._valid_values: set[str] = set()
        for choice in choices:
            if isinstance(choice, tuple):
                self._valid_values.add(choice[0])
            else:
                self._valid_values.add(choice)

    def to_python(self, raw: Any) -> list[str] | None:
        if self._is_empty(raw):
            return []
        if isinstance(raw, list):
            return [str(v) for v in raw]
        # Single value submitted as string
        return [str(raw)]

    def validate(self, value: list[str] | None) -> None:
        if value is None or len(value) == 0:
            if self.required:
                raise FieldValidationError(
                    "Este campo é obrigatório.", code="required"
                )
            return
        for v in value:
            if v not in self._valid_values:
                raise FieldValidationError(
                    f"Selecione apenas opções válidas. '{v}' não é uma das escolhas disponíveis.",
                    code="invalid_choice",
                )
        for validator in self.validators:
            validator(value)


# ---------------------------------------------------------------------------
# File field
# ---------------------------------------------------------------------------


class FileField(Field[Any]):
    """Field that accepts a Starlette ``UploadFile``.

    Does **not** require Pillow or any extra dependency.

    Args:
        max_size: Maximum allowed file size in bytes (``None`` = unlimited).
        allowed_types: Allowed MIME content-types, e.g. ``["image/png", "image/jpeg"]``.
                       ``None`` means any type is accepted.
    """

    default_widget_class = "file"

    def __init__(
        self,
        *,
        max_size: int | None = None,
        allowed_types: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.max_size = max_size
        self.allowed_types = allowed_types

    def to_python(self, raw: Any) -> Any:
        if raw is None:
            return self.default
        return raw  # Return the UploadFile object as-is

    def validate(self, value: Any) -> None:
        if value is None:
            if self.required:
                raise FieldValidationError(
                    "Este campo é obrigatório.", code="required"
                )
            return

        # Validate content type
        content_type: str | None = getattr(value, "content_type", None)
        if self.allowed_types is not None and content_type not in self.allowed_types:
            raise FieldValidationError(
                f"Tipo de arquivo não permitido: '{content_type}'. "
                f"Tipos aceitos: {', '.join(self.allowed_types)}.",
                code="invalid_content_type",
            )

        # Validate size — UploadFile stores size in .size attribute
        size: int | None = getattr(value, "size", None)
        if self.max_size is not None and size is not None and size > self.max_size:
            raise FieldValidationError(
                f"O arquivo é muito grande. Tamanho máximo permitido: {self.max_size} bytes.",
                code="file_too_large",
            )

        for validator in self.validators:
            validator(value)


# ---------------------------------------------------------------------------
# Relational fields (require DB session)
# ---------------------------------------------------------------------------


class ForeignKeyField(Field[Any]):
    """Field that resolves a primary key to a model instance.

    ``to_python()`` raises a ``RuntimeError`` because a DB session is required.
    Use ``to_python_with_session(raw, session)`` instead (called automatically
    by ``AuraForm.full_clean()`` when a session is provided).

    Args:
        model: The SQLAlchemy model class to look up.
        to_field: The field name to match against (default ``"id"``).
        queryset: Optional base queryset (reserved for future filtering).
    """

    def __init__(
        self,
        model: type[Any],
        *,
        to_field: str = "id",
        queryset: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.model = model
        self.to_field = to_field
        self.queryset = queryset

    def to_python(self, raw: Any) -> Any:
        raise RuntimeError(
            f"ForeignKeyField para '{self.model.__name__}' requer uma sessão de banco de dados. "
            "Use AuraForm com session=<session> ou chame "
            "to_python_with_session(raw, session) diretamente."
        )

    async def to_python_with_session(self, raw: Any, session: Any) -> Any:
        """Resolve *raw* PK to a model instance using *session*.

        Raises:
            FieldValidationError: When the object is not found.
        """
        if self._is_empty(raw):
            return self.default

        # Check if raw is already a model instance
        if isinstance(raw, self.model):
            return raw

        pk = raw
        try:
            from sqlalchemy import select as sa_select

            if self.queryset is not None:
                stmt = (
                    self.queryset._build_stmt()
                    if hasattr(self.queryset, "_build_stmt")
                    else self.queryset
                )
            else:
                stmt = sa_select(self.model)

            stmt = stmt.where(getattr(self.model, self.to_field) == pk)
            result = await session.execute(stmt)
            instance = result.scalars().first()
        except Exception as exc:
            raise FieldValidationError(
                f"Erro ao buscar {self.model.__name__} com {self.to_field}={pk!r}: {exc}",
                code="db_error",
            ) from exc

        if instance is None:
            raise FieldValidationError(
                f"{self.model.__name__} com id {pk} não encontrado.",
                code="not_found",
            )
        return instance


class ManyToManyField(Field[list[Any]]):
    """Field that resolves a list of PKs to model instances.

    Like ``ForeignKeyField``, requires a session — ``to_python()`` raises
    ``RuntimeError``.  Use ``to_python_with_session(raw, session)`` instead.

    Args:
        model: The SQLAlchemy model class to look up.
        to_field: The field name to match against (default ``"id"``).
        queryset: Optional base queryset (reserved for future filtering).
        required: Defaults to ``False`` for M2M (empty list is valid).
    """

    def __init__(
        self,
        model: type[Any],
        *,
        to_field: str = "id",
        queryset: Any = None,
        required: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(required=required, **kwargs)
        self.model = model
        self.to_field = to_field
        self.queryset = queryset

    def to_python(self, raw: Any) -> list[Any]:
        raise RuntimeError(
            f"ManyToManyField para '{self.model.__name__}' requer uma sessão de banco de dados. "
            "Use AuraForm com session=<session> ou chame "
            "to_python_with_session(raw, session) diretamente."
        )

    async def to_python_with_session(self, raw: Any, session: Any) -> list[Any]:
        """Resolve a list of PKs to model instances using *session*.

        Raises:
            FieldValidationError: When any of the objects is not found.
        """
        if raw is None:
            return []

        # Check if raw already contains model instances
        if isinstance(raw, list) and all(isinstance(x, self.model) for x in raw):
            return raw
        if isinstance(raw, self.model):
            return [raw]

        pks: list[Any] = raw if isinstance(raw, list) else [raw]
        if not pks:
            return []

        try:
            from sqlalchemy import select as sa_select

            if self.queryset is not None:
                stmt = (
                    self.queryset._build_stmt()
                    if hasattr(self.queryset, "_build_stmt")
                    else self.queryset
                )
            else:
                stmt = sa_select(self.model)

            stmt = stmt.where(getattr(self.model, self.to_field).in_(pks))
            result = await session.execute(stmt)
            instances = list(result.scalars().all())
        except Exception as exc:
            raise FieldValidationError(
                f"Erro ao buscar {self.model.__name__}: {exc}",
                code="db_error",
            ) from exc

        # Verify that all requested primary keys were found
        fetched_pks = {getattr(inst, self.to_field) for inst in instances}
        for pk in pks:
            if pk not in fetched_pks:
                raise FieldValidationError(
                    f"{self.model.__name__} com id {pk} não encontrado.",
                    code="not_found",
                )

        return instances

    def validate(self, value: list[Any] | None) -> None:
        if not value:
            if self.required:
                raise FieldValidationError(
                    "Este campo é obrigatório.", code="required"
                )
            return
        for validator in self.validators:
            validator(value)

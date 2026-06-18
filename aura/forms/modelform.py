"""ModelForm — map SQLAlchemy model columns to AuraForm fields."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar, cast

from sqlalchemy.sql.schema import Column
from sqlalchemy.sql.sqltypes import Boolean, Date, DateTime, Float, Integer, String, Text

from aura.forms.base import AuraForm
from aura.forms.exceptions import FormValidationError
from aura.forms.fields import (
    BoolField,
    CharField,
    DateField,
    DateTimeField,
    Field,
    FloatField,
    IntField,
    TextField,
)
from aura.orm.base import AuraModel

ADMIN_EXCLUDED_COLUMNS = frozenset({"created_at", "updated_at"})

_DATETIME_INPUT_FORMATS = [
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]


def _column_required(col: Column[Any]) -> bool:
    return (
        not col.nullable
        and col.default is None
        and col.server_default is None
    )


def _column_label(col: Column[Any]) -> str:
    return col.name.replace("_", " ").title()


def sqlalchemy_column_to_field(col: Column[Any]) -> Field[Any]:
    """Map a SQLAlchemy column to the matching AuraForm field."""
    required = _column_required(col)
    label = _column_label(col)

    if isinstance(col.type, Boolean):
        return BoolField(required=False, label=label)
    if isinstance(col.type, Integer):
        return IntField(required=required, label=label)
    if isinstance(col.type, Float):
        return FloatField(required=required, label=label)
    if isinstance(col.type, Text):
        return TextField(required=required, label=label)
    if isinstance(col.type, String):
        if col.type.length is None:
            return TextField(required=required, label=label)
        return CharField(required=required, max_length=col.type.length, label=label)
    if isinstance(col.type, DateTime):
        return DateTimeField(
            required=required,
            input_formats=_DATETIME_INPUT_FORMATS,
            label=label,
        )
    if isinstance(col.type, Date):
        return DateField(required=required, label=label)
    return CharField(required=required, label=label)


def iter_model_columns(model: type[AuraModel]) -> list[Column[Any]]:
    """Return editable columns for *model* (no PK / audit timestamps)."""
    return [
        cast(Column[Any], col)
        for col in model.__table__.columns
        if not col.primary_key and col.name not in ADMIN_EXCLUDED_COLUMNS
    ]


def model_form_class(model: type[AuraModel]) -> type[AuraForm]:
    """Build a dynamic :class:`ModelForm` subclass for *model*."""
    field_attrs: dict[str, Field[Any]] = {
        col.name: sqlalchemy_column_to_field(col) for col in iter_model_columns(model)
    }
    meta = type("Meta", (), {"model": model})
    return type(
        f"{model.__name__}Form",
        (ModelForm,),
        {"Meta": meta, **field_attrs},
    )


def form_data_to_raw(model: type[AuraModel], form_data: Any) -> dict[str, Any]:
    """Convert multipart form data into a dict suitable for ModelForm validation."""
    raw: dict[str, Any] = {}
    for col in iter_model_columns(model):
        if isinstance(col.type, Boolean):
            raw[col.name] = form_data.get(col.name)
        else:
            val = form_data.get(col.name)
            if val is not None:
                raw[col.name] = val
    return raw


def _admin_error_message(field_name: str, messages: list[str]) -> str:
    msg = messages[0]
    lowered = msg.lower()
    if "obrigatório" in lowered or "required" in lowered:
        return f"Field '{field_name}' is required."
    return f"Invalid value: {msg}"


async def parse_model_form_data(
    model: type[AuraModel],
    form_data: Any,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate admin form submission via ModelForm.

    Returns:
        A tuple of ``(cleaned_data, errors)`` where *errors* maps field names
        to a single human-readable message (admin template format).
    """
    form_cls = model_form_class(model)
    form = form_cls(raw_data=form_data_to_raw(model, form_data))
    if await form.is_valid():
        return form.cleaned_data, {}

    errors = {
        name: _admin_error_message(name, messages)
        for name, messages in form.errors.items()
        if name != "__all__"
    }
    return {}, errors


def _column_input_meta(col: Column[Any]) -> dict[str, Any]:
    """Map a column type to admin template widget metadata."""
    input_type = "text"
    is_textarea = False
    is_checkbox = False

    if isinstance(col.type, Boolean):
        is_checkbox = True
        input_type = "checkbox"
    elif isinstance(col.type, (Integer, Float)):
        input_type = "number"
    elif isinstance(col.type, Text):
        is_textarea = True
    elif isinstance(col.type, String):
        if col.type.length is None:
            is_textarea = True
        else:
            input_type = "text"
    elif isinstance(col.type, DateTime):
        input_type = "datetime-local"
    elif isinstance(col.type, Date):
        input_type = "date"

    return {
        "input_type": input_type,
        "is_textarea": is_textarea,
        "is_checkbox": is_checkbox,
    }


def _format_field_value(col: Column[Any], value: Any) -> Any:
    if value is None:
        return None
    if isinstance(col.type, DateTime) and isinstance(value, datetime):
        return value.strftime("%Y-%m-%dT%H:%M")
    if isinstance(col.type, Date) and isinstance(value, date):
        return value.isoformat()
    return value


def build_admin_form_fields(
    model: type[AuraModel],
    *,
    values: dict[str, Any] | None = None,
    form_data: Any = None,
    errors: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build the field metadata list consumed by ``admin/templates/form.html``."""
    fields: list[dict[str, Any]] = []
    for col in iter_model_columns(model):
        meta = _column_input_meta(col)
        is_checkbox = meta["is_checkbox"]

        if form_data is not None:
            value: Any = (
                col.name in form_data
                if is_checkbox
                else form_data.get(col.name)
            )
        elif values is not None:
            value = values.get(col.name)
        else:
            value = None

        value = _format_field_value(col, value)

        fields.append({
            "name": col.name,
            "label": _column_label(col),
            "required": _column_required(col),
            "value": value,
            "error": (errors or {}).get(col.name),
            **meta,
        })
    return fields


class ModelForm(AuraForm):
    """Form bound to a SQLAlchemy model — fields are declared on a nested ``Meta``."""

    Meta: ClassVar[type[Any]]

    async def _save(self, *, commit: bool = True) -> Any:
        if not hasattr(self, "Meta") or not hasattr(self.Meta, "model"):
            raise NotImplementedError("ModelForm requires a Meta.model class attribute.")

        model = self.Meta.model
        if self._instance is None:
            self._instance = model(**self.cleaned_data)
            if self._session is not None:
                self._session.add(self._instance)
        else:
            for key, value in self.cleaned_data.items():
                setattr(self._instance, key, value)

        if self._session is not None:
            await self._session.flush()
            if commit:
                await self._session.commit()

        return self._instance

    async def save(self, *, commit: bool = True) -> Any:
        """Validate and persist; raises :class:`FormValidationError` when invalid."""
        if not await self.full_clean():
            raise FormValidationError(self.errors)
        return await self._save(commit=commit)

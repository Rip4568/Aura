# ruff: noqa: N802
"""Semantic field constructor shortcuts for Aura ORM.

These functions act as thin wrappers around SQLAlchemy's ``mapped_column``,
improving developer experience (DX) and conciseness while remaining fully
type-safe and compatible with ``mypy --strict``.
"""

from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import mapped_column, relationship


def CharField(
    max_length: int = 255,
    required: bool = True,
    unique: bool = False,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a VARCHAR database column."""
    return mapped_column(
        String(max_length),
        nullable=not required,
        unique=unique,
        **kwargs,
    )


def TextField(required: bool = True, **kwargs: Any) -> Any:
    """Semantic shortcut for a TEXT database column."""
    return mapped_column(Text, nullable=not required, **kwargs)


def EmailField(
    max_length: int = 254,
    required: bool = True,
    unique: bool = False,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a VARCHAR column intended for e-mails."""
    return mapped_column(
        String(max_length),
        nullable=not required,
        unique=unique,
        **kwargs,
    )


def BooleanField(default: bool = False, **kwargs: Any) -> Any:
    """Semantic shortcut for a BOOLEAN database column."""
    return mapped_column(
        Boolean,
        default=default,
        nullable=False,
        **kwargs,
    )


def IntegerField(
    required: bool = True,
    unique: bool = False,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for an INTEGER database column."""
    return mapped_column(
        Integer,
        nullable=not required,
        unique=unique,
        **kwargs,
    )


def FloatField(
    required: bool = True,
    unique: bool = False,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a FLOAT database column."""
    return mapped_column(
        Float,
        nullable=not required,
        unique=unique,
        **kwargs,
    )


def DecimalField(
    max_digits: int = 10,
    decimal_places: int = 2,
    required: bool = True,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a NUMERIC database column."""
    return mapped_column(
        Numeric(precision=max_digits, scale=decimal_places),
        nullable=not required,
        **kwargs,
    )


def DateTimeField(
    required: bool = True,
    default: Any = None,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a DATETIME database column."""
    return mapped_column(
        DateTime,
        nullable=not required,
        default=default,
        **kwargs,
    )


def DateField(
    required: bool = True,
    default: Any = None,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a DATE database column."""
    return mapped_column(
        Date,
        nullable=not required,
        default=default,
        **kwargs,
    )


def ForeignKeyField(
    model_or_table: Any,
    required: bool = True,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a FOREIGN KEY database column.

    If given a model class, it automatically derives the tablename and appends
    ``.id`` (e.g. ``User`` -> ``users.id``).
    """
    if isinstance(model_or_table, str):
        target = model_or_table
    else:
        tablename = getattr(
            model_or_table,
            "__tablename__",
            model_or_table.__name__.lower() + "s",
        )
        target = f"{tablename}.id"
    return mapped_column(ForeignKey(target), nullable=not required, **kwargs)


def ManyToManyField(
    model_or_name: Any,
    secondary: Any,
    **kwargs: Any,
) -> Any:
    """Semantic shortcut for a Many-to-Many relationship using an association table."""
    return relationship(model_or_name, secondary=secondary, **kwargs)


__all__ = [
    "CharField",
    "TextField",
    "EmailField",
    "BooleanField",
    "IntegerField",
    "FloatField",
    "DecimalField",
    "DateTimeField",
    "DateField",
    "ForeignKeyField",
    "ManyToManyField",
    "relationship",
]


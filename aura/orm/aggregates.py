"""Aggregate functions for QuerySet.aggregate()."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func


class Aggregate:
    """Base class for aggregate functions."""

    def __init__(self, field: str, *, distinct: bool = False) -> None:
        self.field = field
        self.distinct = distinct

    def _to_sqla(self, model: type[Any]) -> Any:
        raise NotImplementedError


class Count(Aggregate):
    """COUNT(field) or COUNT(*) when field='*'."""

    def _to_sqla(self, model: type[Any]) -> Any:
        if self.field == "*":
            return func.count()
        col = getattr(model, self.field)
        return func.count(col.distinct() if self.distinct else col)


class Sum(Aggregate):
    """SUM(field)."""

    def _to_sqla(self, model: type[Any]) -> Any:
        return func.sum(getattr(model, self.field))


class Avg(Aggregate):
    """AVG(field)."""

    def _to_sqla(self, model: type[Any]) -> Any:
        return func.avg(getattr(model, self.field))


class Min(Aggregate):
    """MIN(field)."""

    def _to_sqla(self, model: type[Any]) -> Any:
        return func.min(getattr(model, self.field))


class Max(Aggregate):
    """MAX(field)."""

    def _to_sqla(self, model: type[Any]) -> Any:
        return func.max(getattr(model, self.field))


__all__ = ["Aggregate", "Count", "Sum", "Avg", "Min", "Max"]

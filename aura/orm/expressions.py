"""Q() objects for composing complex filter conditions."""
from __future__ import annotations

from typing import Any

from sqlalchemy import and_, or_


class Q:
    """Encapsulates filter conditions for combination with &, | and ~.

    Examples:
        Q(active=True) | Q(role="admin")
        Q(active=True) & Q(email__endswith="@company.com")
        ~Q(deleted=True)
        (Q(role="admin") | Q(role="moderator")) & ~Q(banned=True)
    """

    def __init__(self, **kwargs: Any) -> None:
        self._conditions: dict[str, Any] = kwargs
        self._connector: str = "AND"
        self._negated: bool = False
        self._children: list[Q] = []

    def __and__(self, other: Q) -> Q:
        q = Q()
        q._connector = "AND"
        q._children = [self, other]
        return q

    def __or__(self, other: Q) -> Q:
        q = Q()
        q._connector = "OR"
        q._children = [self, other]
        return q

    def __invert__(self) -> Q:
        q = Q(**self._conditions)
        q._connector = self._connector
        q._children = list(self._children)
        q._negated = not self._negated
        return q

    def _to_sqla(self, model: type[Any]) -> Any:
        """Compile to a SQLAlchemy expression."""
        from aura.orm.lookups import resolve_lookup

        if self._children:
            compiled = [child._to_sqla(model) for child in self._children]
            expr = and_(*compiled) if self._connector == "AND" else or_(*compiled)
        else:
            parts = [resolve_lookup(model, k, v) for k, v in self._conditions.items()]
            if not parts:
                from sqlalchemy.sql import true
                expr = true()
            elif len(parts) == 1:
                expr = parts[0]
            else:
                expr = and_(*parts)

        return ~expr if self._negated else expr

    def __repr__(self) -> str:
        if self._children:
            op = f" {self._connector} ".join(repr(c) for c in self._children)
            result = f"({op})"
        else:
            result = f"Q({', '.join(f'{k}={v!r}' for k, v in self._conditions.items())})"
        return f"~{result}" if self._negated else result

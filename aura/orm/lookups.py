"""Django-style field lookups for SQLAlchemy expressions."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func

LOOKUPS: dict[str, Any] = {
    "exact":       lambda col, v: col == v,
    "iexact":      lambda col, v: func.lower(col) == func.lower(v),
    "contains":    lambda col, v: col.contains(v),
    "icontains":   lambda col, v: col.ilike(f"%{v}%"),
    "startswith":  lambda col, v: col.startswith(v),
    "istartswith": lambda col, v: col.ilike(f"{v}%"),
    "endswith":    lambda col, v: col.endswith(v),
    "iendswith":   lambda col, v: col.ilike(f"%{v}"),
    "gt":          lambda col, v: col > v,
    "gte":         lambda col, v: col >= v,
    "lt":          lambda col, v: col < v,
    "lte":         lambda col, v: col <= v,
    "in":          lambda col, v: col.in_(v),
    "not_in":      lambda col, v: col.not_in(v),
    "is_null":     lambda col, v: col.is_(None) if v else col.is_not(None),
    "range":       lambda col, v: col.between(v[0], v[1]),
    "year":        lambda col, v: func.strftime("%Y", col) == str(v),
    "month":       lambda col, v: func.strftime("%m", col) == f"{v:02d}",
    "day":         lambda col, v: func.strftime("%d", col) == f"{v:02d}",
}


def resolve_lookup(model: type[Any], key: str, value: Any) -> Any:
    """Resolve 'field' or 'field__lookup' to a SQLAlchemy expression.

    Examples:
        resolve_lookup(User, "name", "alice")           -> User.name == "alice"
        resolve_lookup(User, "name__icontains", "ali")  -> User.name.ilike("%ali%")
        resolve_lookup(User, "age__gte", 18)            -> User.age >= 18
        resolve_lookup(User, "active__is_null", True)   -> User.active IS NULL
    """
    parts = key.split("__")
    field_name = parts[0]
    lookup = parts[1] if len(parts) >= 2 else "exact"

    # FK traversal not supported yet
    if len(parts) >= 3 or (len(parts) == 2 and parts[1] not in LOOKUPS):
        raise NotImplementedError(
            f"FK traversal '{key}' is not supported yet. "
            "Use .join() or raw SQLAlchemy for JOIN-based filtering."
        )

    col = getattr(model, field_name, None)
    if col is None:
        raise AttributeError(
            f"Model '{model.__name__}' has no attribute '{field_name}'. "
            f"Available columns: {[c.key for c in model.__table__.columns]}"
        )

    if lookup not in LOOKUPS:
        raise ValueError(
            f"Unknown lookup '{lookup}'. "
            f"Available: {sorted(LOOKUPS.keys())}"
        )

    return LOOKUPS[lookup](col, value)

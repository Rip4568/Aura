"""
Query profiling and observability for the Aura ORM.

Hooks into SQLAlchemy engine events to capture 100% of queries —
including raw session.execute() calls, not just QuerySet operations.

Usage:
    from aura.orm.profiling import query_log, track_queries

    # Context manager — capture queries in any scope:
    async with query_log() as log:
        users = await repo.list(active=True)
        posts = await post_repo.list()
    print(log.summary())      # "5 queries in 3.2ms · 1 duplicate pattern"
    print(log.count)          # 5
    dupes = log.duplicates()  # queries with same SQL pattern (N+1 smell)

    # Decorator — wrap any async function:
    @track_queries(threshold=5)
    async def list_users(self) -> list[UserResponse]:
        ...
"""
from __future__ import annotations

import contextvars
import functools
import os
import re
import time
import warnings
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])

# ─────────────────────────────────────────────────────────────────────────────
# Semantic warnings
# ─────────────────────────────────────────────────────────────────────────────


class AuraN1Warning(UserWarning):
    """Emitted when duplicate SQL patterns are detected — likely an N+1 query."""


class AuraQueryThresholdWarning(UserWarning):
    """Emitted when query count exceeds the threshold set in @track_queries."""


class AuraSlowQueryWarning(UserWarning):
    """Emitted when a query duration exceeds AURA__QUERY_SLOW_THRESHOLD_MS."""


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class QueryRecord:
    """A single captured query."""

    sql: str
    params: Any
    duration_ms: float


@dataclass
class QueryLog:
    """Collection of queries captured within a scope."""

    queries: list[QueryRecord] = field(default_factory=list)

    def _record(self, sql: str, params: Any, duration_ms: float) -> None:
        self.queries.append(QueryRecord(sql=sql, params=params, duration_ms=duration_ms))
        threshold = _slow_threshold()
        if threshold is not None and duration_ms > threshold:
            warnings.warn(
                f"Slow query ({duration_ms:.1f}ms > {threshold:.0f}ms threshold): "
                f"{sql[:120]}",
                AuraSlowQueryWarning,
                stacklevel=6,
            )

    @property
    def count(self) -> int:
        return len(self.queries)

    @property
    def total_ms(self) -> float:
        return sum(q.duration_ms for q in self.queries)

    @property
    def slowest(self) -> QueryRecord | None:
        """The slowest query in the log."""
        return max(self.queries, key=lambda q: q.duration_ms, default=None)

    def duplicates(self) -> list[QueryRecord]:
        """Queries sharing the same SQL fingerprint — possible N+1 pattern."""
        counts: dict[str, int] = {}
        for q in self.queries:
            fp = _fingerprint(q.sql)
            counts[fp] = counts.get(fp, 0) + 1
        return [q for q in self.queries if counts[_fingerprint(q.sql)] > 1]

    def summary(self) -> str:
        """Human-readable summary line."""
        n = self.count
        parts = [f"{n} {'query' if n == 1 else 'queries'} in {self.total_ms:.1f}ms"]
        dupe_patterns = len({_fingerprint(q.sql) for q in self.duplicates()})
        if dupe_patterns:
            parts.append(f"{dupe_patterns} duplicate pattern(s) [N+1 risk]")
        slow = self.slowest
        if slow and self.count > 1:
            parts.append(f"slowest {slow.duration_ms:.1f}ms")
        return " · ".join(parts)

    def __repr__(self) -> str:
        return f"QueryLog({self.summary()})"


# ─────────────────────────────────────────────────────────────────────────────
# Context var — active log for the current asyncio task
# ─────────────────────────────────────────────────────────────────────────────

_active_log: contextvars.ContextVar[QueryLog | None] = contextvars.ContextVar(
    "_aura_active_query_log", default=None
)

# ─────────────────────────────────────────────────────────────────────────────
# SQLAlchemy engine event hooks
# ─────────────────────────────────────────────────────────────────────────────


def _install_engine_hooks() -> None:
    """Register before/after_cursor_execute listeners on all SQLAlchemy engines.

    These sync events fire even for async engines (SQLAlchemy async wraps sync).
    Overhead when no log is active: ~1 ContextVar lookup per query (~50ns).
    Called once at module import time.
    """
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    # Guard against double-registration
    if getattr(_install_engine_hooks, "_installed", False):
        return
    _install_engine_hooks._installed = True  # type: ignore[attr-defined]

    @event.listens_for(Engine, "before_cursor_execute")
    def _before(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        conn.info.setdefault("_aura_t", []).append(time.perf_counter())

    @event.listens_for(Engine, "after_cursor_execute")
    def _after(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        starts: list[float] = conn.info.get("_aura_t", [])
        if not starts:
            return
        duration_ms = (time.perf_counter() - starts.pop()) * 1000
        log = _active_log.get()
        if log is not None:
            log._record(statement, parameters, duration_ms)


# Install at import time — registering on Engine class catches all engines.
_install_engine_hooks()

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


@asynccontextmanager
async def query_log() -> AsyncIterator[QueryLog]:
    """Async context manager that captures all SQLAlchemy queries in its scope.

    Works with Repository[T], QuerySet, and raw session.execute() calls.
    Nested query_log() contexts are independent — inner logs don't leak to outer.

    Example:
        async with query_log() as log:
            users = await repo.list(active=True)
            posts = await post_repo.list()

        print(log.count)           # 2
        print(log.total_ms)        # 1.8
        print(log.summary())       # "2 queries in 1.8ms"
        dupes = log.duplicates()   # [] (no N+1 here)
    """
    log = QueryLog()
    token = _active_log.set(log)
    try:
        yield log
    finally:
        _active_log.reset(token)


def track_queries(
    func: F | None = None,
    *,
    threshold: int | None = None,
    warn_duplicates: bool = True,
    log_summary: bool = True,
) -> Any:
    """Decorator that profiles query usage in an async function.

    Can be used with or without arguments:

        @track_queries
        async def list_users(self) -> list[User]: ...

        @track_queries(threshold=5, warn_duplicates=True)
        async def create_post(self, data: PostDTO) -> Post: ...

    Emits warnings via Python's warnings module:
    - AuraQueryThresholdWarning: if query count > threshold
    - AuraN1Warning: if duplicate SQL patterns detected
    - AuraSlowQueryWarning: if any query exceeds AURA__QUERY_SLOW_THRESHOLD_MS

    Logs a summary line to stderr in debug mode (AURA__DEBUG=true).
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with query_log() as log:
                result = await fn(*args, **kwargs)

            name = fn.__qualname__

            if threshold is not None and log.count > threshold:
                warnings.warn(
                    f"{name}: {log.count} queries exceeded threshold of {threshold}. "
                    f"({log.total_ms:.1f}ms total) — consider .include() for eager loading.",
                    AuraQueryThresholdWarning,
                    stacklevel=2,
                )

            if warn_duplicates and log.duplicates():
                unique_patterns = len({_fingerprint(q.sql) for q in log.duplicates()})
                warnings.warn(
                    f"{name}: {unique_patterns} duplicate SQL pattern(s) detected "
                    f"({log.count} queries, {log.total_ms:.1f}ms) — likely N+1. "
                    "Use .include() to eager-load relationships.",
                    AuraN1Warning,
                    stacklevel=2,
                )

            if log_summary and os.environ.get("AURA__DEBUG", "").lower() in (
                "1",
                "true",
                "yes",
            ):
                import sys

                print(f"[aura:queries] {name}: {log.summary()}", file=sys.stderr)

            return result

        return wrapper  # type: ignore[return-value]

    if func is not None:
        # Used as @track_queries without parentheses
        return decorator(func)
    return decorator


def setup_query_profiling(engine: Any = None) -> None:
    """Ensure query profiling hooks are installed.

    Called automatically at import time. Safe to call multiple times (idempotent).
    The `engine` parameter is accepted for API compatibility but not required —
    hooks are registered at the Engine class level and apply to all engines.
    """
    _install_engine_hooks()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _fingerprint(sql: str) -> str:
    """Normalize SQL by replacing literal values with '?' for pattern comparison.

    'SELECT ... WHERE id = 1'  → 'SELECT ... WHERE id = ?'
    'SELECT ... WHERE id = 42' → 'SELECT ... WHERE id = ?'
    → same fingerprint → same pattern → N+1 candidate
    """
    # Replace string literals
    sql = re.sub(r"'[^']*'", "?", sql)
    # Replace numeric literals (standalone numbers, not inside words)
    sql = re.sub(r"(?<!\w)\d+(?!\w)", "?", sql)
    # Replace IN (...) lists to normalize variable-length tuples
    sql = re.sub(r"IN\s*\([^)]+\)", "IN (?)", sql, flags=re.IGNORECASE)
    # Normalize whitespace
    return re.sub(r"\s+", " ", sql).strip().upper()


def _slow_threshold() -> float | None:
    """Read AURA__QUERY_SLOW_THRESHOLD_MS from environment."""
    val = os.environ.get("AURA__QUERY_SLOW_THRESHOLD_MS")
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None


__all__ = [
    "QueryLog",
    "QueryRecord",
    "AuraN1Warning",
    "AuraQueryThresholdWarning",
    "AuraSlowQueryWarning",
    "query_log",
    "track_queries",
    "setup_query_profiling",
]

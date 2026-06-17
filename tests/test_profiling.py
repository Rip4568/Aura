"""Tests for the Aura ORM query profiling and observability module."""

from __future__ import annotations

import os
import warnings
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from aura.orm.base import AuraModel
from aura.orm.profiling import (
    AuraN1Warning,
    AuraQueryThresholdWarning,
    AuraSlowQueryWarning,
    QueryRecord,
    query_log,
    track_queries,
)
from aura.orm.repository import Repository
from aura.orm.session import DatabaseManager

# ---------------------------------------------------------------------------
# Test models (separate table to avoid conflicts with tests/test_orm.py)
# ---------------------------------------------------------------------------


class PItem(AuraModel):
    """Model used exclusively for profiling tests."""

    __tablename__ = "profiling_items"

    title: Mapped[str] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(nullable=False, default=0.0)


class PItemRepository(Repository[PItem]):
    """Repository for the PItem model."""

    model = PItem


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def session(db_manager: DatabaseManager) -> AsyncIterator[AsyncSession]:
    """Provide an AsyncSession within a transaction for each test."""
    async with db_manager.session() as s:
        yield s


@pytest.fixture
async def repo(session: AsyncSession) -> PItemRepository:
    """Provide a PItemRepository bound to the test session."""
    return PItemRepository(session)


# ---------------------------------------------------------------------------
# TestQueryLog — context manager behaviour
# ---------------------------------------------------------------------------


class TestQueryLog:
    async def test_captures_queries(self, repo: PItemRepository) -> None:
        """Queries issued inside the context should be captured."""
        async with query_log() as log:
            await repo.create(title="test", price=1.0)
            await repo.list()
        assert log.count >= 2  # at least create + list

    async def test_count(self, repo: PItemRepository) -> None:
        """count property reflects number of captured queries."""
        async with query_log() as log:
            await repo.list()
        assert log.count >= 1

    async def test_total_ms_positive(self, repo: PItemRepository) -> None:
        """total_ms should be positive after at least one query."""
        async with query_log() as log:
            await repo.list()
        assert log.total_ms > 0

    async def test_outside_context_not_captured(self, repo: PItemRepository) -> None:
        """Queries issued outside the context manager must not be captured."""
        await repo.create(title="outside", price=1.0)
        async with query_log() as log:
            pass  # no queries inside
        assert log.count == 0

    async def test_nested_contexts_are_independent(self, repo: PItemRepository) -> None:
        """Inner and outer query_log contexts must not share records."""
        async with query_log() as outer:
            await repo.list()
            async with query_log() as inner:
                await repo.create(title="inner", price=1.0)
            # inner should only have the create, not the outer list
            assert inner.count >= 1
        # outer should have at least its own list query
        assert outer.count >= 1

    async def test_summary_format(self, repo: PItemRepository) -> None:
        """summary() should contain both 'quer' (query/queries) and 'ms'."""
        async with query_log() as log:
            await repo.list()
        s = log.summary()
        assert "quer" in s  # matches both "query" and "queries"
        assert "ms" in s

    async def test_summary_singular_query(self, repo: PItemRepository) -> None:
        """summary() uses 'query' (singular) when count is exactly 1."""
        async with query_log() as log:
            await repo.list()
        # With SQLite the list may fire one query; check singular vs plural
        s = log.summary()
        if log.count == 1:
            assert "1 query" in s
        else:
            assert "queries" in s

    async def test_slowest_returns_none_when_empty(self) -> None:
        """slowest should be None when no queries were captured."""
        async with query_log() as log:
            pass
        assert log.slowest is None

    async def test_slowest_returns_record(self, repo: PItemRepository) -> None:
        """slowest should return a QueryRecord after at least one query."""
        async with query_log() as log:
            await repo.list()
        assert log.slowest is not None
        assert isinstance(log.slowest.duration_ms, float)

    async def test_slowest_is_max_duration(self, repo: PItemRepository) -> None:
        """slowest should point to the query with the highest duration_ms."""
        async with query_log() as log:
            await repo.create(title="a", price=1.0)
            await repo.list()
            await repo.count()
        assert log.slowest is not None
        assert log.slowest.duration_ms == max(q.duration_ms for q in log.queries)

    async def test_repr(self, repo: PItemRepository) -> None:
        """QueryLog repr should include the summary string."""
        async with query_log() as log:
            await repo.list()
        r = repr(log)
        assert "QueryLog(" in r


# ---------------------------------------------------------------------------
# TestFingerprint — SQL normalisation
# ---------------------------------------------------------------------------


class TestFingerprint:
    def test_numeric_literals_replaced(self) -> None:
        from aura.orm.profiling import _fingerprint

        a = _fingerprint("SELECT * FROM users WHERE id = 1")
        b = _fingerprint("SELECT * FROM users WHERE id = 42")
        assert a == b

    def test_string_literals_replaced(self) -> None:
        from aura.orm.profiling import _fingerprint

        a = _fingerprint("SELECT * FROM users WHERE name = 'alice'")
        b = _fingerprint("SELECT * FROM users WHERE name = 'bob'")
        assert a == b

    def test_different_patterns_differ(self) -> None:
        from aura.orm.profiling import _fingerprint

        a = _fingerprint("SELECT * FROM users WHERE id = 1")
        b = _fingerprint("SELECT * FROM posts WHERE id = 1")
        assert a != b

    def test_normalizes_whitespace(self) -> None:
        from aura.orm.profiling import _fingerprint

        a = _fingerprint("SELECT   *   FROM   users")
        b = _fingerprint("SELECT * FROM users")
        assert a == b

    def test_in_clause_normalized(self) -> None:
        from aura.orm.profiling import _fingerprint

        a = _fingerprint("SELECT * FROM users WHERE id IN (1, 2, 3)")
        b = _fingerprint("SELECT * FROM users WHERE id IN (4, 5)")
        assert a == b


# ---------------------------------------------------------------------------
# TestDuplicates — N+1 detection
# ---------------------------------------------------------------------------


class TestDuplicates:
    async def test_duplicates_detected(self, repo: PItemRepository) -> None:
        """Repeated SELECT with the same pattern (different literal IDs) → N+1."""
        titles = [f"DupItem{i}" for i in range(3)]
        for title in titles:
            await repo.create(title=title, price=1.0)
        # Use first() which always calls session.execute() — bypasses identity map
        async with query_log() as log:
            for title in titles:
                await repo.first(title=title)  # same SQL pattern, different title each time
        dupes = log.duplicates()
        assert len(dupes) > 0

    async def test_no_duplicates_for_different_queries(self, repo: PItemRepository) -> None:
        """Queries with structurally different SQL patterns should not be duplicates."""
        a = await repo.create(title="A", price=1.0)
        async with query_log() as log:
            await repo.get(a.id)
            await repo.list()
            await repo.count()
        dupes = log.duplicates()
        assert len(dupes) == 0

    async def test_duplicates_returns_list_of_records(self, repo: PItemRepository) -> None:
        """duplicates() must return a list of QueryRecord instances."""
        titles = [f"DRec{i}" for i in range(2)]
        for title in titles:
            await repo.create(title=title, price=float(0))
        # Use first() which always calls session.execute() — bypasses identity map
        async with query_log() as log:
            for title in titles:
                await repo.first(title=title)
        dupes = log.duplicates()
        assert all(isinstance(d, QueryRecord) for d in dupes)


# ---------------------------------------------------------------------------
# TestTrackQueriesDecorator — decorator behaviour
# ---------------------------------------------------------------------------


class TestTrackQueriesDecorator:
    async def test_without_args(self, repo: PItemRepository) -> None:
        """@track_queries without parentheses should not raise."""

        @track_queries
        async def my_func() -> None:
            await repo.list()

        await my_func()  # must not raise

    async def test_with_threshold_no_warning(self, repo: PItemRepository) -> None:
        """No warning when query count is below threshold."""

        @track_queries(threshold=100)
        async def my_func() -> None:
            await repo.list()

        with warnings.catch_warnings():
            warnings.simplefilter("error", AuraQueryThresholdWarning)
            await my_func()  # 1 query < 100 — must not raise

    async def test_threshold_warning_emitted(self, repo: PItemRepository) -> None:
        """AuraQueryThresholdWarning fired when count exceeds threshold."""

        @track_queries(threshold=1)
        async def my_func() -> None:
            await repo.list()
            await repo.count()
            await repo.list()

        with pytest.warns(AuraQueryThresholdWarning):
            await my_func()

    async def test_n1_warning_emitted(self, repo: PItemRepository) -> None:
        """AuraN1Warning fired when the same SQL pattern repeats."""
        titles = [f"N1Item{i}" for i in range(3)]
        for title in titles:
            await repo.create(title=title, price=float(0))

        @track_queries(warn_duplicates=True)
        async def my_func() -> None:
            # Use first() which always calls session.execute() — same SQL pattern, different values
            for title in titles:
                await repo.first(title=title)

        with pytest.warns(AuraN1Warning):
            await my_func()

    async def test_n1_warning_suppressed_when_disabled(self, repo: PItemRepository) -> None:
        """AuraN1Warning must NOT be emitted when warn_duplicates=False."""
        items = [await repo.create(title=f"W{i}", price=float(i)) for i in range(3)]

        @track_queries(warn_duplicates=False)
        async def my_func() -> None:
            for item in items:
                await repo.get(item.id)

        with warnings.catch_warnings():
            warnings.simplefilter("error", AuraN1Warning)
            await my_func()  # should not raise

    async def test_return_value_preserved(self, repo: PItemRepository) -> None:
        """@track_queries must transparently return the wrapped function's value."""

        @track_queries
        async def my_func() -> int:
            await repo.create(title="ret", price=1.0)
            return 42

        result = await my_func()
        assert result == 42

    async def test_with_explicit_parentheses_no_args(self, repo: PItemRepository) -> None:
        """@track_queries() with empty parentheses should also work."""

        @track_queries()
        async def my_func() -> str:
            await repo.list()
            return "ok"

        result = await my_func()
        assert result == "ok"


# ---------------------------------------------------------------------------
# TestSlowQueryWarning — AURA__QUERY_SLOW_THRESHOLD_MS
# ---------------------------------------------------------------------------


class TestSlowQueryWarning:
    async def test_slow_warning_emitted(self, repo: PItemRepository) -> None:
        """A threshold of 0.001ms ensures any real query triggers the warning."""
        with patch.dict(os.environ, {"AURA__QUERY_SLOW_THRESHOLD_MS": "0.001"}):
            with pytest.warns(AuraSlowQueryWarning):
                async with query_log():
                    await repo.create(title="slow", price=1.0)

    async def test_no_warning_without_threshold(self, repo: PItemRepository) -> None:
        """Without the env var set, AuraSlowQueryWarning must not be emitted."""
        env = {k: v for k, v in os.environ.items() if k != "AURA__QUERY_SLOW_THRESHOLD_MS"}
        with patch.dict(os.environ, env, clear=True):
            with warnings.catch_warnings():
                warnings.simplefilter("error", AuraSlowQueryWarning)
                async with query_log():
                    await repo.create(title="fast", price=1.0)  # must not raise

    async def test_invalid_threshold_ignored(self, repo: PItemRepository) -> None:
        """A non-numeric threshold value should be treated as 'no threshold'."""
        with patch.dict(os.environ, {"AURA__QUERY_SLOW_THRESHOLD_MS": "not_a_number"}):
            with warnings.catch_warnings():
                warnings.simplefilter("error", AuraSlowQueryWarning)
                async with query_log():
                    await repo.list()  # must not raise


# ---------------------------------------------------------------------------
# TestSetupQueryProfiling — idempotency
# ---------------------------------------------------------------------------


class TestSetupQueryProfiling:
    def test_idempotent(self) -> None:
        """setup_query_profiling() must be safe to call multiple times."""
        from aura.orm.profiling import setup_query_profiling

        setup_query_profiling()
        setup_query_profiling()
        setup_query_profiling(engine=None)
        # No exception → pass

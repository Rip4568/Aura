"""Tests for AuraQL — fluent async query builder (QuerySet, Q, lookups)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aura.orm.aggregates import Avg, Count, Max, Min, Sum
from aura.orm.base import AuraModel
from aura.orm.expressions import Q
from aura.orm.query import MultipleObjectsReturnedException, QuerySet
from aura.orm.session import DatabaseManager

# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class QBAuthor(AuraModel):
    """Author model for QueryBuilder tests."""

    __tablename__ = "qb_authors"

    name: Mapped[str] = mapped_column(nullable=False)
    email: Mapped[str] = mapped_column(nullable=False, default="")

    posts: Mapped[list[QBPost]] = relationship("QBPost", back_populates="author")


class QBPost(AuraModel):
    """Post model for QueryBuilder tests."""

    __tablename__ = "qb_posts"

    title: Mapped[str] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(default=True)
    view_count: Mapped[int] = mapped_column(default=0)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("qb_authors.id"), nullable=True
    )

    author: Mapped[QBAuthor | None] = relationship("QBAuthor", back_populates="posts")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_manager() -> AsyncIterator[DatabaseManager]:
    """Fresh in-memory SQLite DatabaseManager with qb_authors and qb_posts tables."""
    manager = DatabaseManager()
    manager.init("sqlite+aiosqlite:///:memory:", echo=False)
    async with manager._engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(AuraModel.metadata.create_all)
    yield manager
    async with manager._engine.begin() as conn:  # type: ignore[union-attr]
        await conn.run_sync(AuraModel.metadata.drop_all)
    await manager.close()


@pytest.fixture
async def session(db_manager: DatabaseManager) -> AsyncIterator[AsyncSession]:
    """AsyncSession within a transaction rolled back after each test."""
    async with db_manager.session() as s:
        yield s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_author(session: AsyncSession, name: str, email: str = "") -> QBAuthor:
    author = QBAuthor(name=name, email=email or f"{name.lower()}@example.com")
    session.add(author)
    await session.flush()
    await session.refresh(author)
    return author


async def _create_post(
    session: AsyncSession,
    title: str,
    active: bool = True,
    view_count: int = 0,
    author_id: int | None = None,
) -> QBPost:
    post = QBPost(title=title, active=active, view_count=view_count, author_id=author_id)
    session.add(post)
    await session.flush()
    await session.refresh(post)
    return post


# ---------------------------------------------------------------------------
# TestBasic
# ---------------------------------------------------------------------------


class TestBasic:
    """Basic QuerySet operations: all, filter, exclude, order_by, limit, offset, page."""

    async def test_all_empty(self, session: AsyncSession) -> None:
        results = await QBPost.objects.using(session).all()
        assert results == []

    async def test_all_returns_inserted(self, session: AsyncSession) -> None:
        await _create_post(session, "Post A")
        await _create_post(session, "Post B")
        results = await QBPost.objects.using(session).all()
        assert len(results) == 2

    async def test_filter_equality(self, session: AsyncSession) -> None:
        await _create_post(session, "Active", active=True)
        await _create_post(session, "Inactive", active=False)
        results = await QBPost.objects.using(session).filter(active=True).all()
        assert len(results) == 1
        assert results[0].title == "Active"

    async def test_filter_with_q_or(self, session: AsyncSession) -> None:
        await _create_post(session, "Alpha", active=True)
        await _create_post(session, "Beta", active=False)
        await _create_post(session, "Gamma", active=True)
        results = await (
            QBPost.objects.using(session)
            .filter(Q(title="Alpha") | Q(title="Beta"))
            .all()
        )
        titles = {r.title for r in results}
        assert titles == {"Alpha", "Beta"}

    async def test_filter_with_q_not(self, session: AsyncSession) -> None:
        await _create_post(session, "Delete Me", active=True)
        await _create_post(session, "Keep Me", active=False)
        results = await (
            QBPost.objects.using(session)
            .filter(~Q(title="Delete Me"))
            .all()
        )
        assert len(results) == 1
        assert results[0].title == "Keep Me"

    async def test_exclude(self, session: AsyncSession) -> None:
        await _create_post(session, "Excluded", active=True)
        await _create_post(session, "Kept", active=False)
        results = await QBPost.objects.using(session).exclude(active=True).all()
        assert len(results) == 1
        assert results[0].title == "Kept"

    async def test_order_by_asc(self, session: AsyncSession) -> None:
        await _create_post(session, "B Post", view_count=2)
        await _create_post(session, "A Post", view_count=1)
        results = await QBPost.objects.using(session).order_by("view_count").all()
        assert results[0].view_count <= results[1].view_count

    async def test_order_by_desc(self, session: AsyncSession) -> None:
        await _create_post(session, "Low", view_count=1)
        await _create_post(session, "High", view_count=99)
        results = await QBPost.objects.using(session).order_by("-view_count").all()
        assert results[0].view_count > results[1].view_count

    async def test_limit(self, session: AsyncSession) -> None:
        for i in range(5):
            await _create_post(session, f"Post {i}")
        results = await QBPost.objects.using(session).limit(2).all()
        assert len(results) == 2

    async def test_offset(self, session: AsyncSession) -> None:
        for i in range(5):
            await _create_post(session, f"Post {i}")
        first_two = await QBPost.objects.using(session).limit(2).all()
        next_two = await QBPost.objects.using(session).offset(2).limit(2).all()
        assert {r.id for r in first_two}.isdisjoint({r.id for r in next_two})

    async def test_page(self, session: AsyncSession) -> None:
        for i in range(6):
            await _create_post(session, f"Post {i}")
        page1 = await QBPost.objects.using(session).page(1, 2).all()
        page2 = await QBPost.objects.using(session).page(2, 2).all()
        assert len(page1) == 2
        assert len(page2) == 2
        assert {r.id for r in page1}.isdisjoint({r.id for r in page2})

    async def test_distinct(self, session: AsyncSession) -> None:
        await _create_post(session, "Dup", active=True)
        await _create_post(session, "Dup", active=True)
        # distinct on the full row — just verify it doesn't error
        results = await QBPost.objects.using(session).distinct().all()
        assert len(results) >= 1

    async def test_immutability(self, session: AsyncSession) -> None:
        """filter() should not mutate the original QuerySet."""
        base = QBPost.objects.using(session)
        filtered = base.filter(active=True)
        assert base._filters == []
        assert len(filtered._filters) == 1


# ---------------------------------------------------------------------------
# TestLookups
# ---------------------------------------------------------------------------


class TestLookups:
    """Django-style lookup tests."""

    async def test_icontains(self, session: AsyncSession) -> None:
        await _create_post(session, "Hello World")
        await _create_post(session, "Goodbye")
        results = await QBPost.objects.using(session).filter(title__icontains="hello").all()
        assert len(results) == 1
        assert results[0].title == "Hello World"

    async def test_gte(self, session: AsyncSession) -> None:
        await _create_post(session, "Low", view_count=5)
        await _create_post(session, "High", view_count=10)
        results = await QBPost.objects.using(session).filter(view_count__gte=10).all()
        assert len(results) == 1
        assert results[0].title == "High"

    async def test_lte(self, session: AsyncSession) -> None:
        await _create_post(session, "Low", view_count=5)
        await _create_post(session, "High", view_count=10)
        results = await QBPost.objects.using(session).filter(view_count__lte=5).all()
        assert len(results) == 1
        assert results[0].title == "Low"

    async def test_gt(self, session: AsyncSession) -> None:
        await _create_post(session, "Low", view_count=5)
        await _create_post(session, "High", view_count=10)
        results = await QBPost.objects.using(session).filter(view_count__gt=5).all()
        assert len(results) == 1
        assert results[0].title == "High"

    async def test_lt(self, session: AsyncSession) -> None:
        await _create_post(session, "Low", view_count=5)
        await _create_post(session, "High", view_count=10)
        results = await QBPost.objects.using(session).filter(view_count__lt=10).all()
        assert len(results) == 1
        assert results[0].title == "Low"

    async def test_in_list(self, session: AsyncSession) -> None:
        p1 = await _create_post(session, "P1")
        p2 = await _create_post(session, "P2")
        await _create_post(session, "P3")
        results = await QBPost.objects.using(session).filter(id__in=[p1.id, p2.id]).all()
        assert len(results) == 2

    async def test_is_null_true(self, session: AsyncSession) -> None:
        await _create_post(session, "No Author", author_id=None)
        author = await _create_author(session, "Alice")
        await _create_post(session, "With Author", author_id=author.id)
        results = await QBPost.objects.using(session).filter(author_id__is_null=True).all()
        assert all(r.author_id is None for r in results)

    async def test_is_null_false(self, session: AsyncSession) -> None:
        await _create_post(session, "No Author", author_id=None)
        author = await _create_author(session, "Bob")
        await _create_post(session, "With Author", author_id=author.id)
        results = await QBPost.objects.using(session).filter(author_id__is_null=False).all()
        assert all(r.author_id is not None for r in results)

    async def test_range(self, session: AsyncSession) -> None:
        await _create_post(session, "VL", view_count=1)
        await _create_post(session, "VM", view_count=5)
        await _create_post(session, "VH", view_count=10)
        results = await QBPost.objects.using(session).filter(view_count__range=[3, 7]).all()
        assert len(results) == 1
        assert results[0].title == "VM"

    async def test_startswith(self, session: AsyncSession) -> None:
        await _create_post(session, "Hello World")
        await _create_post(session, "World Hello")
        results = await QBPost.objects.using(session).filter(title__startswith="Hello").all()
        assert len(results) == 1

    async def test_endswith(self, session: AsyncSession) -> None:
        await _create_post(session, "Hello World")
        await _create_post(session, "World Hello")
        results = await QBPost.objects.using(session).filter(title__endswith="Hello").all()
        assert len(results) == 1
        assert results[0].title == "World Hello"

    async def test_iexact(self, session: AsyncSession) -> None:
        await _create_post(session, "UPPER POST")
        results = await QBPost.objects.using(session).filter(title__iexact="upper post").all()
        assert len(results) == 1

    async def test_contains(self, session: AsyncSession) -> None:
        await _create_post(session, "Exact Case Match")
        results = await QBPost.objects.using(session).filter(title__contains="Case").all()
        assert len(results) == 1


# ---------------------------------------------------------------------------
# TestTerminal
# ---------------------------------------------------------------------------


class TestTerminal:
    """Terminal method tests: first, last, get, get_or_none, count, exists."""

    async def test_first_returns_item(self, session: AsyncSession) -> None:
        await _create_post(session, "First Post")
        result = await QBPost.objects.using(session).first()
        assert result is not None

    async def test_first_returns_none_when_empty(self, session: AsyncSession) -> None:
        result = await QBPost.objects.using(session).first()
        assert result is None

    async def test_last_returns_item(self, session: AsyncSession) -> None:
        await _create_post(session, "Post A")
        await _create_post(session, "Post B")
        result = await QBPost.objects.using(session).last()
        assert result is not None

    async def test_get_found(self, session: AsyncSession) -> None:
        post = await _create_post(session, "Unique Post")
        result = await QBPost.objects.using(session).get(id=post.id)
        assert result.id == post.id

    async def test_get_not_found_raises(self, session: AsyncSession) -> None:
        from aura.exceptions.http import NotFoundException
        with pytest.raises(NotFoundException):
            await QBPost.objects.using(session).get(id=99999)

    async def test_get_multiple_raises(self, session: AsyncSession) -> None:
        await _create_post(session, "Dup Title", active=True)
        await _create_post(session, "Dup Title", active=True)
        with pytest.raises(MultipleObjectsReturnedException):
            await QBPost.objects.using(session).get(title="Dup Title")

    async def test_get_or_none_found(self, session: AsyncSession) -> None:
        post = await _create_post(session, "Exists Post")
        result = await QBPost.objects.using(session).get_or_none(id=post.id)
        assert result is not None
        assert result.id == post.id

    async def test_get_or_none_returns_none(self, session: AsyncSession) -> None:
        result = await QBPost.objects.using(session).get_or_none(id=99999)
        assert result is None

    async def test_count_all(self, session: AsyncSession) -> None:
        await _create_post(session, "P1")
        await _create_post(session, "P2")
        count = await QBPost.objects.using(session).count()
        assert count == 2

    async def test_count_with_filter(self, session: AsyncSession) -> None:
        await _create_post(session, "Active", active=True)
        await _create_post(session, "Active2", active=True)
        await _create_post(session, "Inactive", active=False)
        count = await QBPost.objects.using(session).filter(active=True).count()
        assert count == 2

    async def test_exists_true(self, session: AsyncSession) -> None:
        await _create_post(session, "Exists")
        result = await QBPost.objects.using(session).exists()
        assert result is True

    async def test_exists_false(self, session: AsyncSession) -> None:
        result = await QBPost.objects.using(session).exists()
        assert result is False

    async def test_exists_with_filter_true(self, session: AsyncSession) -> None:
        await _create_post(session, "Has Views", view_count=5)
        result = await QBPost.objects.using(session).filter(view_count__gt=0).exists()
        assert result is True

    async def test_exists_with_filter_false(self, session: AsyncSession) -> None:
        await _create_post(session, "No Views", view_count=0)
        result = await QBPost.objects.using(session).filter(view_count__gt=100).exists()
        assert result is False

    async def test_last_respects_order_by_ascending(self, session: AsyncSession) -> None:
        """last() should respect ascending order_by and return highest value."""
        await _create_post(session, "Post A", view_count=10)
        await _create_post(session, "Post B", view_count=20)
        post_c = await _create_post(session, "Post C", view_count=30)

        result = await QBPost.objects.using(session).order_by("view_count").last()
        assert result is not None
        assert result.id == post_c.id
        assert result.view_count == 30

    async def test_last_respects_order_by_descending(self, session: AsyncSession) -> None:
        """last() should respect descending order_by and return lowest value."""
        post_a = await _create_post(session, "Post A", view_count=10)
        await _create_post(session, "Post B", view_count=20)
        await _create_post(session, "Post C", view_count=30)

        result = await QBPost.objects.using(session).order_by("-view_count").last()
        assert result is not None
        assert result.id == post_a.id
        assert result.view_count == 10

    async def test_last_defaults_to_desc_id_when_no_order_by(
        self, session: AsyncSession
    ) -> None:
        """last() should default to desc(id) when no order_by is specified."""
        await _create_post(session, "Post A")
        post_b = await _create_post(session, "Post B")

        result = await QBPost.objects.using(session).last()
        assert result is not None
        assert result.id == post_b.id


# ---------------------------------------------------------------------------
# TestPaginate
# ---------------------------------------------------------------------------


class TestPaginate:
    """Tests for QuerySet.paginate()."""

    async def test_paginate_page1(self, session: AsyncSession) -> None:
        for i in range(5):
            await _create_post(session, f"Post {i}")
        result = await QBPost.objects.using(session).paginate(page=1, per_page=2)
        assert result.page == 1
        assert result.per_page == 2
        assert result.total == 5
        assert len(result.items) == 2
        assert result.has_next is True

    async def test_paginate_last_page(self, session: AsyncSession) -> None:
        for i in range(5):
            await _create_post(session, f"Post {i}")
        result = await QBPost.objects.using(session).paginate(page=3, per_page=2)
        assert len(result.items) == 1
        assert result.has_next is False

    async def test_paginate_has_next_true(self, session: AsyncSession) -> None:
        for i in range(10):
            await _create_post(session, f"Post {i}")
        result = await QBPost.objects.using(session).paginate(page=1, per_page=5)
        assert result.has_next is True

    async def test_paginate_has_next_false(self, session: AsyncSession) -> None:
        for i in range(4):
            await _create_post(session, f"Post {i}")
        result = await QBPost.objects.using(session).paginate(page=1, per_page=10)
        assert result.has_next is False

    async def test_paginate_empty(self, session: AsyncSession) -> None:
        result = await QBPost.objects.using(session).paginate()
        assert result.total == 0
        assert result.items == []
        assert result.has_next is False


# ---------------------------------------------------------------------------
# TestBulkOps
# ---------------------------------------------------------------------------


class TestBulkOps:
    """Tests for QuerySet.delete() and QuerySet.update()."""

    async def test_delete_with_filter(self, session: AsyncSession) -> None:
        await _create_post(session, "Delete Me", active=True)
        await _create_post(session, "Keep Me", active=False)
        count = await QBPost.objects.using(session).filter(active=True).delete()
        assert count == 1
        remaining = await QBPost.objects.using(session).all()
        assert len(remaining) == 1
        assert remaining[0].title == "Keep Me"

    async def test_delete_all(self, session: AsyncSession) -> None:
        await _create_post(session, "P1")
        await _create_post(session, "P2")
        count = await QBPost.objects.using(session).delete(allow_unfiltered=True)
        assert count == 2
        remaining = await QBPost.objects.using(session).all()
        assert remaining == []

    async def test_delete_all_without_allow_unfiltered_raises(
        self, session: AsyncSession
    ) -> None:
        """delete() without filters and allow_unfiltered=False should raise ValueError."""
        await _create_post(session, "P1")
        await _create_post(session, "P2")

        with pytest.raises(ValueError, match="Bulk delete of all records is not allowed"):
            await QBPost.objects.using(session).delete()

    async def test_update_with_filter(self, session: AsyncSession) -> None:
        await _create_post(session, "Old Title", active=True)
        await _create_post(session, "Other", active=False)
        count = await QBPost.objects.using(session).filter(active=True).update(title="New Title")
        assert count == 1
        updated = await QBPost.objects.using(session).filter(title="New Title").first()
        assert updated is not None

    async def test_update_bulk(self, session: AsyncSession) -> None:
        await _create_post(session, "P1", active=True)
        await _create_post(session, "P2", active=True)
        count = await QBPost.objects.using(session).filter(active=True).update(view_count=100)
        assert count == 2


# ---------------------------------------------------------------------------
# TestEagerLoading
# ---------------------------------------------------------------------------


class TestEagerLoading:
    """Tests that include() and select_related() load relationships without errors."""

    async def test_include_loads_relationship(self, session: AsyncSession) -> None:
        """include() should preload posts on QBAuthor without N+1 or DetachedInstanceError."""
        author = await _create_author(session, "Alice")
        await _create_post(session, "Post by Alice", author_id=author.id)
        await _create_post(session, "Post by Alice 2", author_id=author.id)

        authors = await QBAuthor.objects.using(session).include("posts").all()
        assert len(authors) == 1
        # Access relationship inside session — should not raise
        assert len(authors[0].posts) == 2

    async def test_select_related_loads_relationship(self, session: AsyncSession) -> None:
        """select_related() should preload author on QBPost using joinedload."""
        author = await _create_author(session, "Bob")
        await _create_post(session, "Bob's Post", author_id=author.id)

        posts = await QBPost.objects.using(session).select_related("author").all()
        assert len(posts) == 1
        assert posts[0].author is not None
        assert posts[0].author.name == "Bob"

    async def test_include_multiple_relationships(self, session: AsyncSession) -> None:
        """include() with multiple relationship names should not error."""
        author = await _create_author(session, "Carol")
        await _create_post(session, "Carol Post", author_id=author.id)
        # QBAuthor has only 'posts' relationship — test that include handles it
        authors = await QBAuthor.objects.using(session).include("posts").all()
        assert len(authors[0].posts) >= 1

    async def test_posts_with_no_author_include(self, session: AsyncSession) -> None:
        """Posts with null author_id should still load with select_related."""
        await _create_post(session, "Orphan Post", author_id=None)
        posts = await QBPost.objects.using(session).select_related("author").all()
        assert len(posts) == 1
        assert posts[0].author is None


# ---------------------------------------------------------------------------
# TestDebug
# ---------------------------------------------------------------------------


class TestDebug:
    """Tests for sql() and explain() debug helpers."""

    async def test_sql_returns_string(self, session: AsyncSession) -> None:
        sql = QBPost.objects.using(session).sql()
        assert isinstance(sql, str)
        assert "qb_posts" in sql.lower() or "SELECT" in sql

    async def test_sql_contains_where_with_filter(self, session: AsyncSession) -> None:
        sql = QBPost.objects.using(session).filter(active=True).sql()
        assert "WHERE" in sql.upper() or "where" in sql.lower()

    async def test_sql_contains_limit(self, session: AsyncSession) -> None:
        sql = QBPost.objects.using(session).limit(5).sql()
        assert "5" in sql

    async def test_using_without_session_raises(self) -> None:
        qs: QuerySet[QBPost] = QBPost.objects
        with pytest.raises(RuntimeError, match="no session"):
            await qs.all()

    async def test_queryset_repr(self, session: AsyncSession) -> None:
        qs = QBPost.objects.using(session)
        assert "QBPost" in repr(qs)

    async def test_q_repr(self) -> None:
        q = Q(active=True) | Q(title="Test")
        assert "OR" in repr(q)

    async def test_q_negation_repr(self) -> None:
        q = ~Q(active=True)
        assert "~" in repr(q)

    async def test_explain_returns_string(self, session: AsyncSession) -> None:
        """explain() should return a non-empty string from SQLite EXPLAIN QUERY PLAN."""
        await _create_post(session, "Explain Post")
        result = await QBPost.objects.using(session).explain()
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# TestQObject
# ---------------------------------------------------------------------------


class TestQObject:
    """Unit tests for Q object composition without DB."""

    def test_q_and(self) -> None:
        q = Q(active=True) & Q(view_count=0)
        assert q._connector == "AND"
        assert len(q._children) == 2

    def test_q_or(self) -> None:
        q = Q(active=True) | Q(view_count=0)
        assert q._connector == "OR"
        assert len(q._children) == 2

    def test_q_invert(self) -> None:
        q = ~Q(active=True)
        assert q._negated is True

    def test_q_double_invert(self) -> None:
        q = ~~Q(active=True)
        assert q._negated is False

    async def test_q_and_filter(self, session: AsyncSession) -> None:
        await _create_post(session, "Match", active=True, view_count=5)
        await _create_post(session, "Miss A", active=False, view_count=5)
        await _create_post(session, "Miss B", active=True, view_count=0)
        results = await (
            QBPost.objects.using(session)
            .filter(Q(active=True) & Q(view_count__gt=0))
            .all()
        )
        assert len(results) == 1
        assert results[0].title == "Match"

    async def test_q_complex_expression(self, session: AsyncSession) -> None:
        """(Q(active=True) | Q(view_count__gt=50)) & ~Q(title__icontains='skip')"""
        await _create_post(session, "Keep active", active=True, view_count=0)
        await _create_post(session, "skip this", active=True, view_count=0)
        await _create_post(session, "High views", active=False, view_count=100)
        results = await (
            QBPost.objects.using(session)
            .filter((Q(active=True) | Q(view_count__gt=50)) & ~Q(title__icontains="skip"))
            .all()
        )
        titles = {r.title for r in results}
        assert "Keep active" in titles
        assert "High views" in titles
        assert "skip this" not in titles


# ---------------------------------------------------------------------------
# TestAggregate
# ---------------------------------------------------------------------------


class TestAggregate:
    """Tests for QuerySet.aggregate() and Aggregate functions."""

    async def test_count_all(self, session: AsyncSession) -> None:
        for i in range(4):
            await _create_post(session, f"P{i}", view_count=i * 10)
        result = await QBPost.objects.using(session).aggregate(total=Count("id"))
        assert result["total"] == 4

    async def test_count_star(self, session: AsyncSession) -> None:
        await _create_post(session, "A", view_count=1)
        await _create_post(session, "B", view_count=2)
        result = await QBPost.objects.using(session).aggregate(total=Count("*"))
        assert result["total"] == 2

    async def test_sum(self, session: AsyncSession) -> None:
        await _create_post(session, "A", view_count=10)
        await _create_post(session, "B", view_count=30)
        result = await QBPost.objects.using(session).aggregate(total=Sum("view_count"))
        assert result["total"] == 40

    async def test_avg(self, session: AsyncSession) -> None:
        await _create_post(session, "A", view_count=10)
        await _create_post(session, "B", view_count=30)
        result = await QBPost.objects.using(session).aggregate(avg=Avg("view_count"))
        assert result["avg"] == 20.0

    async def test_min(self, session: AsyncSession) -> None:
        await _create_post(session, "A", view_count=5)
        await _create_post(session, "B", view_count=15)
        result = await QBPost.objects.using(session).aggregate(minimum=Min("view_count"))
        assert result["minimum"] == 5

    async def test_max(self, session: AsyncSession) -> None:
        await _create_post(session, "A", view_count=5)
        await _create_post(session, "B", view_count=15)
        result = await QBPost.objects.using(session).aggregate(maximum=Max("view_count"))
        assert result["maximum"] == 15

    async def test_multiple_aggregates(self, session: AsyncSession) -> None:
        for v in [10, 20, 30]:
            await _create_post(session, f"P{v}", view_count=v)
        result = await QBPost.objects.using(session).aggregate(
            total=Count("id"),
            total_views=Sum("view_count"),
            avg_views=Avg("view_count"),
            min_views=Min("view_count"),
            max_views=Max("view_count"),
        )
        assert result["total"] == 3
        assert result["total_views"] == 60
        assert result["avg_views"] == 20.0
        assert result["min_views"] == 10
        assert result["max_views"] == 30

    async def test_aggregate_with_filter(self, session: AsyncSession) -> None:
        await _create_post(session, "Active", active=True, view_count=100)
        await _create_post(session, "Inactive", active=False, view_count=200)
        result = await (
            QBPost.objects.using(session)
            .filter(active=True)
            .aggregate(total=Count("id"), views=Sum("view_count"))
        )
        assert result["total"] == 1
        assert result["views"] == 100

    async def test_aggregate_wrong_type_raises(self, session: AsyncSession) -> None:
        with pytest.raises(TypeError, match="Aggregate"):
            await QBPost.objects.using(session).aggregate(bad="not_an_aggregate")


# ---------------------------------------------------------------------------
# TestValues
# ---------------------------------------------------------------------------


class TestValues:
    """Tests for QuerySet.values() and QuerySet.values_list()."""

    async def test_values_specific_fields(self, session: AsyncSession) -> None:
        await _create_post(session, "Alpha", view_count=10)
        await _create_post(session, "Beta", view_count=20)
        rows = await QBPost.objects.using(session).order_by("title").values("title", "view_count")
        assert rows == [
            {"title": "Alpha", "view_count": 10},
            {"title": "Beta", "view_count": 20},
        ]

    async def test_values_all_fields(self, session: AsyncSession) -> None:
        await _create_post(session, "Gamma")
        rows = await QBPost.objects.using(session).values()
        assert len(rows) == 1
        assert "id" in rows[0]
        assert "title" in rows[0]

    async def test_values_with_filter(self, session: AsyncSession) -> None:
        await _create_post(session, "Active", active=True)
        await _create_post(session, "Inactive", active=False)
        rows = await QBPost.objects.using(session).filter(active=True).values("title")
        assert rows == [{"title": "Active"}]

    async def test_values_list_single_field(self, session: AsyncSession) -> None:
        await _create_post(session, "A")
        await _create_post(session, "B")
        rows = await QBPost.objects.using(session).order_by("title").values_list("title")
        assert rows == [("A",), ("B",)]

    async def test_values_list_flat(self, session: AsyncSession) -> None:
        await _create_post(session, "X")
        await _create_post(session, "Y")
        titles = await (
            QBPost.objects.using(session).order_by("title").values_list("title", flat=True)
        )
        assert titles == ["X", "Y"]

    async def test_values_list_multiple_fields(self, session: AsyncSession) -> None:
        await _create_post(session, "Post1", view_count=5)
        rows = await QBPost.objects.using(session).values_list("title", "view_count")
        assert rows == [("Post1", 5)]

    async def test_values_list_flat_multiple_raises(self, session: AsyncSession) -> None:
        with pytest.raises(ValueError, match="exactly one field"):
            await QBPost.objects.using(session).values_list("title", "view_count", flat=True)

    async def test_values_list_no_fields_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one field"):
            await QBPost.objects.values_list()


# ---------------------------------------------------------------------------
# TestQueryBuilderFixes (Newly added to cover our fixes)
# ---------------------------------------------------------------------------

class TestQueryBuilderFixes:
    async def test_bulk_delete_with_limit_raises_value_error(self, session: AsyncSession) -> None:
        with pytest.raises(ValueError, match="limited, offset, or ordered"):
            await QBPost.objects.using(session).limit(2).delete()

    async def test_bulk_update_with_limit_raises_value_error(self, session: AsyncSession) -> None:
        with pytest.raises(ValueError, match="limited, offset, or ordered"):
            await QBPost.objects.using(session).limit(2).update(active=False)

    async def test_values_distinct(self, session: AsyncSession) -> None:
        await _create_post(session, "Dup", view_count=10)
        await _create_post(session, "Dup", view_count=10)
        rows = await (
            QBPost.objects.using(session)
            .filter(title="Dup")
            .distinct()
            .values("title")
        )
        assert len(rows) == 1

    async def test_values_list_distinct(self, session: AsyncSession) -> None:
        await _create_post(session, "Dup", view_count=10)
        await _create_post(session, "Dup", view_count=10)
        rows = await (
            QBPost.objects.using(session)
            .filter(title="Dup")
            .distinct()
            .values_list("title", flat=True)
        )
        assert len(rows) == 1

"""Tests for the Aura ORM layer (Repository, DatabaseManager, AuraModel)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from aura.orm.base import AuraModel
from aura.orm.repository import Page, Repository
from aura.orm.session import DatabaseManager

# ---------------------------------------------------------------------------
# Test model
# ---------------------------------------------------------------------------

class Item(AuraModel):
    """Simple model for testing."""

    __tablename__ = "items"

    title: Mapped[str] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(nullable=False, default=0.0)
    active: Mapped[bool] = mapped_column(default=True)


class ItemRepository(Repository[Item]):
    """Repository for the Item model."""

    model = Item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_manager() -> AsyncIterator[DatabaseManager]:
    """Provide a fresh in-memory SQLite DatabaseManager for each test."""
    manager = DatabaseManager()
    manager.init("sqlite+aiosqlite:///:memory:", echo=False)
    await manager.create_all(AuraModel)
    yield manager
    await manager.drop_all(AuraModel)
    await manager.close()


@pytest.fixture
async def session(db_manager: DatabaseManager) -> AsyncIterator[AsyncSession]:
    """Provide an AsyncSession within a transaction that is rolled back after the test."""
    async with db_manager.session() as s:
        yield s


@pytest.fixture
async def repo(session: AsyncSession) -> ItemRepository:
    """Provide an ItemRepository bound to the test session."""
    return ItemRepository(session)


# ---------------------------------------------------------------------------
# DatabaseManager
# ---------------------------------------------------------------------------

class TestDatabaseManager:
    """Tests for DatabaseManager session lifecycle."""

    async def test_session_context_manager(self, db_manager: DatabaseManager) -> None:
        async with db_manager.session() as session:
            assert session is not None

    async def test_uninitialised_raises(self) -> None:
        manager = DatabaseManager()
        with pytest.raises(RuntimeError, match="not initialised"):
            async with manager.session():
                pass

    async def test_repr(self) -> None:
        manager = DatabaseManager()
        assert "uninitialised" in repr(manager)
        manager.init("sqlite+aiosqlite:///:memory:")
        assert "initialised" in repr(manager)
        await manager.close()

    async def test_close_idempotent(self) -> None:
        """DatabaseManager.close() should be safe to call multiple times."""
        manager = DatabaseManager()
        manager.init("sqlite+aiosqlite:///:memory:")
        await manager.close()
        # Should not raise when called again on an already-closed manager
        await manager.close()


# ---------------------------------------------------------------------------
# AuraModel
# ---------------------------------------------------------------------------

class TestAuraModel:
    """Tests for the AuraModel base class."""

    async def test_repr(self, repo: ItemRepository) -> None:
        item = await repo.create(title="Widget", price=9.99)
        assert "Item" in repr(item)
        assert str(item.id) in repr(item)

    async def test_to_dict(self, repo: ItemRepository) -> None:
        item = await repo.create(title="Gadget", price=19.99)
        d = item.to_dict()
        assert d["title"] == "Gadget"
        assert d["price"] == 19.99
        assert "id" in d
        assert "created_at" in d
        assert "updated_at" in d


# ---------------------------------------------------------------------------
# Repository CRUD
# ---------------------------------------------------------------------------

class TestRepository:
    """Tests for the generic Repository class."""

    async def test_create(self, repo: ItemRepository) -> None:
        item = await repo.create(title="Notebook", price=5.0)
        assert item.id is not None
        assert item.title == "Notebook"
        assert item.price == 5.0

    async def test_get_existing(self, repo: ItemRepository) -> None:
        item = await repo.create(title="Pen", price=1.5)
        fetched = await repo.get(item.id)
        assert fetched is not None
        assert fetched.id == item.id

    async def test_get_nonexistent_returns_none(self, repo: ItemRepository) -> None:
        result = await repo.get(99999)
        assert result is None

    async def test_get_or_raise_found(self, repo: ItemRepository) -> None:
        item = await repo.create(title="Eraser", price=0.5)
        fetched = await repo.get_or_raise(item.id)
        assert fetched.id == item.id

    async def test_get_or_raise_missing(self, repo: ItemRepository) -> None:
        with pytest.raises(Exception):  # NotFoundException or similar
            await repo.get_or_raise(99999)

    async def test_list_all(self, repo: ItemRepository) -> None:
        await repo.create(title="A", price=1.0)
        await repo.create(title="B", price=2.0)
        items = await repo.list()
        assert len(items) >= 2

    async def test_list_with_filter(self, repo: ItemRepository) -> None:
        await repo.create(title="Active", price=1.0, active=True)
        await repo.create(title="Inactive", price=1.0, active=False)
        active_items = await repo.list(active=True)
        assert all(i.active for i in active_items)

    async def test_list_limit_offset(self, repo: ItemRepository) -> None:
        for i in range(5):
            await repo.create(title=f"Item {i}", price=float(i))
        first_two = await repo.list(limit=2, offset=0)
        next_two = await repo.list(limit=2, offset=2)
        assert len(first_two) == 2
        assert len(next_two) == 2
        assert {i.id for i in first_two}.isdisjoint({i.id for i in next_two})

    async def test_update(self, repo: ItemRepository) -> None:
        item = await repo.create(title="Old Title", price=1.0)
        updated = await repo.update(item.id, title="New Title")
        assert updated.title == "New Title"
        assert updated.id == item.id

    async def test_delete_existing(self, repo: ItemRepository) -> None:
        item = await repo.create(title="Delete Me", price=0.0)
        deleted = await repo.delete(item.id)
        assert deleted is True
        assert await repo.get(item.id) is None

    async def test_delete_nonexistent(self, repo: ItemRepository) -> None:
        result = await repo.delete(99999)
        assert result is False

    async def test_exists_true(self, repo: ItemRepository) -> None:
        await repo.create(title="Exists", price=1.0)
        assert await repo.exists(title="Exists") is True

    async def test_exists_false(self, repo: ItemRepository) -> None:
        assert await repo.exists(title="Does Not Exist") is False

    async def test_count(self, repo: ItemRepository) -> None:
        initial = await repo.count()
        await repo.create(title="C1", price=1.0)
        await repo.create(title="C2", price=2.0)
        assert await repo.count() == initial + 2

    async def test_count_with_filter(self, repo: ItemRepository) -> None:
        await repo.create(title="Priced", price=10.0)
        await repo.create(title="Priced2", price=10.0)
        await repo.create(title="Other", price=5.0)
        assert await repo.count(price=10.0) == 2

    async def test_first(self, repo: ItemRepository) -> None:
        await repo.create(title="First", price=0.0)
        item = await repo.first(title="First")
        assert item is not None
        assert item.title == "First"

    async def test_first_no_match(self, repo: ItemRepository) -> None:
        result = await repo.first(title="__no_match__")
        assert result is None

    async def test_bulk_create(self, repo: ItemRepository) -> None:
        items_data = [
            {"title": "Bulk1", "price": 1.0},
            {"title": "Bulk2", "price": 2.0},
            {"title": "Bulk3", "price": 3.0},
        ]
        items = await repo.bulk_create(items_data)
        assert len(items) == 3
        assert all(i.id is not None for i in items)
        titles = {i.title for i in items}
        assert titles == {"Bulk1", "Bulk2", "Bulk3"}


# ---------------------------------------------------------------------------
# Repository.paginate()
# ---------------------------------------------------------------------------

class TestPaginate:
    """Tests for Repository.paginate() and the Page dataclass."""

    async def test_paginate_returns_page_object(self, repo: ItemRepository) -> None:
        for i in range(5):
            await repo.create(title=f"Item {i}", price=float(i))
        result = await repo.paginate(page=1, per_page=2)
        assert isinstance(result, Page)
        assert len(result.items) == 2
        assert result.total == 5
        assert result.page == 1
        assert result.per_page == 2
        assert result.has_next is True

    async def test_paginate_last_page(self, repo: ItemRepository) -> None:
        for i in range(5):
            await repo.create(title=f"Item {i}", price=float(i))
        # page=3, per_page=2 → offset=4, so only 1 item remains
        result = await repo.paginate(page=3, per_page=2)
        assert len(result.items) == 1
        assert result.total == 5
        assert result.has_next is False

    async def test_paginate_with_filter(self, repo: ItemRepository) -> None:
        for i in range(3):
            await repo.create(title=f"Active {i}", price=float(i), active=True)
        for i in range(2):
            await repo.create(title=f"Inactive {i}", price=float(i), active=False)
        result = await repo.paginate(active=True)
        assert result.total == 3
        assert all(item.active for item in result.items)

    async def test_paginate_empty(self, repo: ItemRepository) -> None:
        result = await repo.paginate()
        assert result.total == 0
        assert result.items == []
        assert result.has_next is False


# ---------------------------------------------------------------------------
# DatabaseManager.transaction()
# ---------------------------------------------------------------------------

class TestTransaction:
    """Tests for the DatabaseManager.transaction() context manager."""

    async def test_transaction_commits_on_success(self, db_manager: DatabaseManager) -> None:
        async with db_manager.transaction() as session:
            repo = ItemRepository(session)
            await repo.create(title="Tx Item 1", price=1.0)
            await repo.create(title="Tx Item 2", price=2.0)

        # verify in a separate session
        async with db_manager.session() as session:
            repo = ItemRepository(session)
            items = await repo.list()
        assert len(items) == 2
        titles = {i.title for i in items}
        assert titles == {"Tx Item 1", "Tx Item 2"}

    async def test_transaction_rollback_on_exception(self, db_manager: DatabaseManager) -> None:
        with pytest.raises(ValueError, match="intentional"):
            async with db_manager.transaction() as session:
                repo = ItemRepository(session)
                await repo.create(title="Should Not Exist", price=9.0)
                raise ValueError("intentional rollback")

        # verify nothing was persisted
        async with db_manager.session() as session:
            repo = ItemRepository(session)
            items = await repo.list()
        assert len(items) == 0

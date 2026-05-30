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

    async def test_parallel_execution(self, db_manager: DatabaseManager) -> None:
        """Test that db.parallel executes multiple callables concurrently in separate sessions."""
        # Insert some items first
        async with db_manager.session() as s:
            repo = ItemRepository(s)
            await repo.create(title="Item A", price=10.0)
            await repo.create(title="Item B", price=20.0)

        # Execute parallel queries
        res_a, res_b = await db_manager.parallel(
            lambda s: ItemRepository(s).first(title="Item A"),
            lambda s: ItemRepository(s).first(title="Item B"),
        )
        assert res_a is not None
        assert res_a.title == "Item A"
        assert res_b is not None
        assert res_b.title == "Item B"



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
        from aura.exceptions.http import NotFoundException
        with pytest.raises(NotFoundException):
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

    async def test_bulk_update(self, repo: ItemRepository) -> None:
        a = await repo.create(title="A", price=1.0)
        b = await repo.create(title="B", price=2.0)
        updated = await repo.bulk_update([a.id, b.id], active=False)
        assert len(updated) == 2
        assert all(not u.active for u in updated)

    async def test_bulk_update_raises_on_missing_id(self, repo: ItemRepository) -> None:
        from aura.exceptions.http import NotFoundException
        with pytest.raises(NotFoundException):
            await repo.bulk_update([99999], title="Ghost")

    async def test_bulk_delete(self, repo: ItemRepository) -> None:
        a = await repo.create(title="Del A", price=1.0)
        b = await repo.create(title="Del B", price=2.0)
        count = await repo.bulk_delete([a.id, b.id])
        assert count == 2
        assert await repo.get(a.id) is None
        assert await repo.get(b.id) is None

    async def test_bulk_delete_skips_missing(self, repo: ItemRepository) -> None:
        a = await repo.create(title="Exists", price=1.0)
        count = await repo.bulk_delete([a.id, 99999])
        assert count == 1  # only the existing one was deleted

    async def test_list_order_by_ascending(self, repo: ItemRepository) -> None:
        await repo.create(title="C", price=3.0)
        await repo.create(title="A", price=1.0)
        await repo.create(title="B", price=2.0)
        items = await repo.list(order_by="price")
        prices = [i.price for i in items]
        assert prices == sorted(prices)

    async def test_list_order_by_descending(self, repo: ItemRepository) -> None:
        await repo.create(title="C", price=3.0)
        await repo.create(title="A", price=1.0)
        await repo.create(title="B", price=2.0)
        items = await repo.list(order_by="-price")
        prices = [i.price for i in items]
        assert prices == sorted(prices, reverse=True)

    async def test_list_order_by_nonexistent_field_raises(self, repo: ItemRepository) -> None:
        from aura.exceptions.http import UnprocessableEntityException
        with pytest.raises(UnprocessableEntityException, match="Unknown order_by field"):
            await repo.list(order_by="nonexistent")

    async def test_list_filter_nonexistent_field_raises(self, repo: ItemRepository) -> None:
        from aura.exceptions.http import UnprocessableEntityException
        with pytest.raises(UnprocessableEntityException, match="Unknown filter field"):
            await repo.list(nonexistent_field="value")

    async def test_bulk_create_empty_list(self, repo: ItemRepository) -> None:
        result = await repo.bulk_create([])
        assert result == []

    async def test_bulk_update_empty_list(self, repo: ItemRepository) -> None:
        result = await repo.bulk_update([])
        assert result == []

    async def test_bulk_delete_empty_list(self, repo: ItemRepository) -> None:
        result = await repo.bulk_delete([])
        assert result == 0


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

    async def test_paginate_page_zero_raises(self, repo: ItemRepository) -> None:
        from aura.exceptions.http import UnprocessableEntityException
        with pytest.raises(UnprocessableEntityException, match="Page must be >= 1"):
            await repo.paginate(page=0)

    async def test_paginate_negative_page_raises(self, repo: ItemRepository) -> None:
        from aura.exceptions.http import UnprocessableEntityException
        with pytest.raises(UnprocessableEntityException, match="Page must be >= 1"):
            await repo.paginate(page=-1)


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

        async with db_manager.session() as session:
            repo = ItemRepository(session)
            items = await repo.list()
        assert len(items) == 0


# ---------------------------------------------------------------------------
# DatabaseMiddleware & Scoped DI
# ---------------------------------------------------------------------------

class ScopedService:
    pass

class SingletonService:
    def __init__(self, scoped: ScopedService) -> None:
        self.scoped = scoped


class TestDatabaseMiddleware:
    """Tests for the DatabaseMiddleware transaction lifecycle and scoped DI."""

    async def test_middleware_transaction_lifecycle_success(
        self,
        db_manager: DatabaseManager,
    ) -> None:
        """Test that DatabaseMiddleware commits on successful requests."""
        from sqlalchemy.ext.asyncio import AsyncSession
        from starlette.types import Receive, Scope, Send

        from aura.di.container import DIContainer
        from aura.middleware.di import DIRequestScopeMiddleware
        from aura.orm.middleware import DatabaseMiddleware
        from aura.orm.session import db

        # Initialize the global db so that DatabaseMiddleware doesn't bypass it
        db.init("sqlite+aiosqlite:///:memory:", echo=False)
        await db.create_all(AuraModel)

        try:
            # 1. Setup app and container
            container = DIContainer()
            class MockApp:
                class State:
                    pass
                state = State()
            mock_app = MockApp()
            mock_app.state.container = container

            # 2. Mock handler and middleware chain
            async def mock_endpoint(scope: Scope, receive: Receive, send: Send) -> None:
                # Inside the request scope, resolve the session from the container
                scoped_container = scope["state"]["container"]
                session = await scoped_container.resolve(AsyncSession)
                assert session is not None
                repo = ItemRepository(session)
                await repo.create(title="Auto Persisted", price=42.0)

            # Build middleware chain: DI scoping -> DB session -> Endpoint
            db_mw = DatabaseMiddleware(mock_endpoint)
            di_mw = DIRequestScopeMiddleware(db_mw)

            # 3. Trigger simulated ASGI request
            scope: Scope = {
                "type": "http",
                "app": mock_app,
                "method": "POST",
                "path": "/test",
                "state": {},
            }
            async def dummy_receive() -> dict: return {}
            async def dummy_send(event: dict) -> None: pass

            # Run the request
            await di_mw(scope, dummy_receive, dummy_send)

            # 4. Verify in a separate session that transaction committed successfully
            async with db.session() as s:
                repo = ItemRepository(s)
                items = await repo.list()
            assert len(items) == 1
            assert items[0].price == 42.0
        finally:
            await db.close()

    async def test_captive_dependency_protection(self) -> None:
        """Test captive dependency protection error."""
        from aura.di.container import DIContainer, Lifetime

        container = DIContainer()
        container.register(ScopedService, lifetime=Lifetime.SCOPED)
        container.register(SingletonService, lifetime=Lifetime.SINGLETON)

        # Resolving the SingletonService should raise a captive dependency error
        with pytest.raises(RuntimeError, match="Captive dependency detected"):
            await container.resolve(SingletonService)



"""Tests for the Aura Seeder infrastructure."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.orm import Mapped, mapped_column

from aura.di import injectable
from aura.di.container import Lifetime, container
from aura.orm.base import AuraModel
from aura.orm.seeders import (
    Seeder,
    ensure_seeded_table_exists,
    has_seeded,
    mark_as_seeded,
)
from aura.orm.session import DatabaseManager, current_session, db

# ---------------------------------------------------------------------------
# Test model
# ---------------------------------------------------------------------------


class SeederItem(AuraModel):
    """Simple model for testing seeders."""

    __tablename__ = "seeder_items"

    name: Mapped[str] = mapped_column(nullable=False)


# ---------------------------------------------------------------------------
# Test services
# ---------------------------------------------------------------------------


class SeedDependency:
    """A dummy dependency to test DI resolution in seeders."""

    def __init__(self) -> None:
        self.value = "injected"


# ---------------------------------------------------------------------------
# Seeders definitions
# ---------------------------------------------------------------------------


@injectable
class ChildSeeder(Seeder):
    """Seeder that writes an item using DI dependency."""

    def __init__(self, dep: SeedDependency) -> None:
        self.dep = dep

    async def run(self) -> None:
        item = SeederItem(name=f"child_{self.dep.value}")
        await self.save(item)


@injectable
class MainSeeder(Seeder):
    """Main seeder calling child seeder."""

    async def run(self) -> None:
        item = SeederItem(name="main_start")
        await self.save(item)
        await self.call([ChildSeeder])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_db() -> AsyncIterator[DatabaseManager]:
    """Provide a fresh in-memory SQLite DatabaseManager for seeder tests."""
    original_engine = db._engine
    original_factory = db._session_factory

    db.init("sqlite+aiosqlite:///:memory:", echo=False)
    await db.create_all(AuraModel)

    yield db

    await db.drop_all(AuraModel)
    await db.close()

    db._engine = original_engine
    db._session_factory = original_factory


# ---------------------------------------------------------------------------
# Seeder Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ensure_seeded_table_exists_and_idempotency(test_db: DatabaseManager) -> None:
    """Test seeder metadata table creation and idempotency helper functions."""
    async with test_db.session() as session:
        # Table should not exist yet, let's create it
        await ensure_seeded_table_exists(session)

        # Check that it starts as not seeded
        is_seeded = await has_seeded(session, "TestSeeder")
        assert is_seeded is False

        # Mark as seeded
        await mark_as_seeded(session, "TestSeeder")
        await session.commit()

    async with test_db.session() as session:
        # Check that it is now seeded
        is_seeded = await has_seeded(session, "TestSeeder")
        assert is_seeded is True


@pytest.mark.asyncio
async def test_seeder_execution_with_di_and_save(test_db: DatabaseManager) -> None:
    """Test full seeder execution flow with DI, child call and saving."""
    # Register our dependency in the global container
    container.register(SeedDependency, lifetime=Lifetime.SINGLETON)

    async with test_db.session() as session:
        await ensure_seeded_table_exists(session)

        # Propagate session via contextvar
        token = current_session.set(session)
        try:
            # Let's resolve and run the MainSeeder
            if not container.is_registered(MainSeeder):
                container.register(MainSeeder)

            seeder = await container.resolve(MainSeeder)
            await seeder.run()
        finally:
            current_session.reset(token)

        await session.commit()

    # Now verify the items were inserted in the database
    async with test_db.session() as session:
        from sqlalchemy import select

        stmt = select(SeederItem)
        result = await session.execute(stmt)
        items = list(result.scalars().all())

        assert len(items) == 2
        names = {item.name for item in items}
        assert names == {"main_start", "child_injected"}

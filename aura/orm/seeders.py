"""Seeder infrastructure for the Aura framework."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import Column, DateTime, MetaData, String, Table, select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.di import injectable
from aura.di.container import Lifetime, container
from aura.orm.session import current_session, db

# SQLAlchemy Core Table for seeding metadata
metadata = MetaData()
seeded_table = Table(
    "_aura_seeded",
    metadata,
    Column("class_name", String(255), primary_key=True),
    Column(
        "seeded_at",
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    ),
)


async def ensure_seeded_table_exists(session: AsyncSession) -> None:
    """Ensure the database table for tracking seeded classes exists.

    Args:
        session: An active async SQLAlchemy session.
    """
    connection = await session.connection()
    await connection.run_sync(metadata.create_all, tables=[seeded_table])


async def has_seeded(session: AsyncSession, class_name: str) -> bool:
    """Check if a seeder class has already been executed.

    Args:
        session: An active async SQLAlchemy session.
        class_name: The fully qualified or simple class name of the seeder.

    Returns:
        True if the seeder has already run, False otherwise.
    """
    stmt = select(seeded_table.c.class_name).where(seeded_table.c.class_name == class_name)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def mark_as_seeded(session: AsyncSession, class_name: str) -> None:
    """Mark a seeder class as executed in the metadata table.

    Args:
        session: An active async SQLAlchemy session.
        class_name: The name of the seeder class.
    """
    stmt = seeded_table.insert().values(class_name=class_name)
    await session.execute(stmt)


@injectable
class Seeder:
    """Base class for all database seeders.

    Seeders can run raw SQL, populate models, and trigger other seeders.
    They support dynamic dependency injection from the container.
    """

    async def run(self) -> None:
        """Run the database seeding logic.

        Must be overridden by subclasses.
        """
        raise NotImplementedError("Seeders must implement a run() method.")

    async def call(self, seeders: list[type[Seeder]]) -> None:
        """Resolve and execute child seeders dynamically using the DI container.

        Args:
            seeders: A list of Seeder classes to resolve and run.
        """
        for seeder_cls in seeders:
            if not container.is_registered(seeder_cls):
                meta = getattr(seeder_cls, "__aura_injectable__", None)
                lifetime = meta["lifetime"] if meta else Lifetime.SINGLETON
                container.register(seeder_cls, lifetime=lifetime)

            seeder_instance = await container.resolve(seeder_cls)
            await seeder_instance.run()

    async def save(self, obj: Any) -> None:
        """Save a model instance transparently.

        Uses the active dynamic transaction from the context, or fallback to a new
        one created from db.session() if no active session is found.

        Args:
            obj: The database model instance or object to save.
        """
        session = current_session.get()
        if session is not None:
            session.add(obj)
            await session.flush()
        else:
            async with db.session() as sess:
                sess.add(obj)

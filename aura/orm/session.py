"""SQLAlchemy async session management for Aura."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseManager:
    """Manages async database engine creation and session lifecycle.

    A single :class:`DatabaseManager` instance is typically shared globally
    (see module-level ``db`` singleton below) and initialised once during
    application startup.

    Args:
        None — call :meth:`init` after construction.

    Example::

        from aura.orm import db

        # In your app startup hook:
        db.init("sqlite+aiosqlite:///app.db", echo=False)

        # In a request handler or service:
        async with db.session() as session:
            user = await session.get(User, 1)
    """

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def init(self, url: str, **kwargs: Any) -> None:
        """Initialise the engine and session factory.

        Args:
            url: SQLAlchemy async database URL, e.g.
                 ``"postgresql+asyncpg://user:pass@localhost/db"`` or
                 ``"sqlite+aiosqlite:///./app.db"``.
            **kwargs: Extra keyword arguments forwarded to
                      :func:`create_async_engine` (e.g. ``echo=True``).
        """
        self._engine = create_async_engine(url, **kwargs)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        """The underlying async engine.

        Raises:
            RuntimeError: If :meth:`init` has not been called.
        """
        if self._engine is None:
            raise RuntimeError("DatabaseManager not initialised — call db.init() first.")
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Async context manager that yields a transactional session.

        Commits automatically on exit; rolls back on any exception.

        Raises:
            RuntimeError: If :meth:`init` has not been called.

        Yields:
            An :class:`~sqlalchemy.ext.asyncio.AsyncSession`.
        """
        if self._session_factory is None:
            raise RuntimeError("DatabaseManager not initialised — call db.init() first.")
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def create_all(self, base: Any) -> None:
        """Create all tables defined in *base*.metadata.

        Convenience method for development/testing — use Alembic for
        production migrations.

        Args:
            base: The :class:`~sqlalchemy.orm.DeclarativeBase` subclass
                  whose metadata should be used.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(base.metadata.create_all)

    async def drop_all(self, base: Any) -> None:
        """Drop all tables defined in *base*.metadata.

        Args:
            base: The :class:`~sqlalchemy.orm.DeclarativeBase` subclass.
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(base.metadata.drop_all)

    async def close(self) -> None:
        """Dispose the engine and release all connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def __repr__(self) -> str:
        status = "initialised" if self._engine else "uninitialised"
        return f"<DatabaseManager [{status}]>"


# ---------------------------------------------------------------------------
# Module-level singleton — initialised by the Aura app on startup.
# ---------------------------------------------------------------------------
db = DatabaseManager()

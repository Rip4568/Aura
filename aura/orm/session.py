"""SQLAlchemy async session management for Aura."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

T = TypeVar("T")


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
        try:
            from aura.orm.profiling import setup_query_profiling

            setup_query_profiling(self._engine)
        except Exception:  # pragma: no cover
            pass

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

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Async context manager for a unit-of-work spanning multiple repositories.

        Commits on clean exit; rolls back on any exception.
        Semantically equivalent to :meth:`session` — use this name when the
        intent is coordinating writes across more than one repository.

        Raises:
            RuntimeError: If :meth:`init` has not been called.

        Yields:
            A shared :class:`~sqlalchemy.ext.asyncio.AsyncSession`.
        """
        async with self.session() as s:
            yield s

    async def parallel(self, *callables: Callable[[AsyncSession], Awaitable[T]]) -> list[T]:
        """Execute multiple database queries or functions concurrently in parallel.

        Each callable is executed within its own isolated, transactional database
        session, allowing secure parallel query execution via the connection pool.

        Args:
            *callables: Coroutines or functions accepting an
                        :class:`AsyncSession` as their sole argument.

        Returns:
            A list containing the gathered results in the same order as the callables.

        Example::

            users, posts = await db.parallel(
                lambda s: UserRepository(s).list(),
                lambda s: PostRepository(s).list(),
            )
        """
        import asyncio

        async def run_one(cb: Callable[[AsyncSession], Awaitable[T]]) -> T:
            async with self.session() as session:
                return await cb(session)

        return list(await asyncio.gather(*(run_one(cb) for cb in callables)))

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

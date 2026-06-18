"""Shared pytest fixtures for the Aura test suite."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Generator
from typing import Any, cast

import pytest

from aura import Aura
from aura.orm.base import AuraModel
from aura.orm.session import DatabaseManager
from aura.testing.client import AuraTestClient


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio as the anyio backend for all tests."""
    return "asyncio"


def make_app(**kwargs: Any) -> Aura:
    """Create a minimal :class:`~aura.core.app.Aura` instance for testing.

    Any keyword arguments are forwarded to :class:`~aura.core.app.Aura`.
    """
    return Aura(**kwargs)


@pytest.fixture
def simple_app() -> Aura:
    """A minimal Aura application with no modules for basic tests."""
    return make_app(title="Test App")


@pytest.fixture
async def client(simple_app: Aura) -> AsyncIterator[AuraTestClient]:
    """An AuraTestClient targeting the ``simple_app`` fixture."""
    async with AuraTestClient(simple_app) as ac:
        yield ac


@pytest.fixture
async def db_manager() -> AsyncIterator[DatabaseManager]:
    """Provide a fresh in-memory SQLite DatabaseManager for each test."""
    manager = DatabaseManager()
    manager.init("sqlite+aiosqlite:///:memory:", echo=False)
    await manager.create_all(AuraModel)
    yield manager
    await manager.drop_all(AuraModel)
    await manager.close()


@pytest.fixture(autouse=True)
def reset_global_state() -> Generator[None, None, None]:
    """Reset global ``db`` and ``container`` singletons between tests."""
    import asyncio

    from aura.di.container import container as global_container
    from aura.orm.session import db as global_db

    orig_engine = global_db._engine
    orig_factory = global_db._session_factory
    orig_providers = dict(global_container._providers)
    orig_scoped = dict(global_container._scoped_cache)

    global_db._engine = None
    global_db._session_factory = None
    global_container._providers.clear()
    global_container._scoped_cache.clear()

    yield

    if global_db._engine is not None and global_db._engine is not orig_engine:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(global_db.close())
        else:
            new_loop = asyncio.new_event_loop()
            try:
                new_loop.run_until_complete(global_db.close())
            finally:
                new_loop.close()

    global_db._engine = orig_engine
    global_db._session_factory = orig_factory
    global_container._providers = orig_providers
    global_container._scoped_cache = orig_scoped


@pytest.fixture(autouse=True)
def reset_task_registry() -> Generator[None, None, None]:
    """Reset TaskRegistry before and after each test.
    
    This ensures that tasks registered in one test do not leak into other tests,
    preventing test pollution and isolation issues.
    """
    from aura.jobs.base import TaskRegistry
    
    TaskRegistry.clear()
    yield
    TaskRegistry.clear()


@pytest.fixture(autouse=True)
def reset_logging() -> Generator[None, None, None]:
    """Reset logging configuration before each test.

    This ensures that tests are isolated and logging configuration
    from one test doesn't affect another.
    """
    # Import here to avoid circular imports
    from aura.logging.logger import Log

    # Reset Log singleton
    cast(Any, Log)._set_instance(None)

    # Reset root logger
    root_logger = logging.getLogger()
    original_level = root_logger.level
    original_handlers = root_logger.handlers[:]

    # Reset aura.app logger
    aura_logger = logging.getLogger("aura.app")
    aura_logger.handlers.clear()
    aura_logger.setLevel(logging.NOTSET)

    yield

    # Cleanup after test
    root_logger.setLevel(original_level)
    # Remove added handlers, restore original ones
    for handler in root_logger.handlers[:]:
        if handler not in original_handlers:
            root_logger.removeHandler(handler)
    cast(Any, Log)._set_instance(None)
    aura_logger.handlers.clear()

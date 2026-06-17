"""Shared pytest fixtures for the Aura test suite."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Generator
from typing import Any, cast

import pytest

from aura import Aura
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

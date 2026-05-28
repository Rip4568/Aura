"""Shared pytest fixtures for the Aura test suite."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from aura import Aura


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
async def client(simple_app: Aura) -> AsyncClient:  # type: ignore[misc]
    """An httpx AsyncClient targeting the ``simple_app`` fixture."""
    async with AsyncClient(
        transport=ASGITransport(app=simple_app),
        base_url="http://testserver",
    ) as ac:
        yield ac

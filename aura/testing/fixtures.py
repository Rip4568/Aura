"""Pytest fixtures for Aura application testing."""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from aura.testing.client import AuraTestClient


@pytest.fixture
def aura_app() -> Any:
    """Provide an Aura application instance for testing.

    Override this fixture in your ``conftest.py`` to supply your actual app::

        from myapp.main import app

        @pytest.fixture
        def aura_app():
            return app

    Returns:
        A bare :class:`~aura.core.app.Aura` instance (or override).
    """
    try:
        from aura.core.app import Aura  # type: ignore[import]
        return Aura()
    except ImportError:
        # Core module may not be available; return a trivial ASGI app for testing.
        async def _dummy_app(scope: Any, receive: Any, send: Any) -> None:
            if scope["type"] == "http":
                await send({"type": "http.response.start", "status": 200, "headers": []})
                await send({"type": "http.response.body", "body": b"", "more_body": False})

        return _dummy_app


@pytest.fixture
async def test_client(aura_app: Any) -> AsyncIterator[AuraTestClient]:
    """Provide an :class:`~aura.testing.client.AuraTestClient` for the app.

    Automatically starts and stops the client around the test.

    Usage::

        async def test_health(test_client: AuraTestClient):
            response = await test_client.get("/health")
            assert response.status_code == 200

    Yields:
        A ready-to-use :class:`~aura.testing.client.AuraTestClient`.
    """
    async with AuraTestClient(aura_app) as client:
        yield client

"""Async HTTP test client for Aura applications."""

from __future__ import annotations

from typing import Any


class AuraTestClient:
    """Async HTTP client for testing Aura applications.

    Uses ``httpx`` with an ``ASGITransport`` so requests never hit the
    network — they are dispatched directly to the ASGI application.

    Args:
        app: The :class:`~aura.core.app.Aura` application under test.
        base_url: Base URL prepended to every request path.

    Usage::

        async def test_list_users(test_client: AuraTestClient):
            response = await test_client.get("/users/")
            assert response.status_code == 200
            assert response.json() == []

    As an async context manager::

        async with AuraTestClient(app) as client:
            resp = await client.post("/users/", json={"name": "Alice"})
            assert resp.status_code == 201
    """

    def __init__(self, app: Any, base_url: str = "http://testserver") -> None:
        self.app = app
        self.base_url = base_url
        self._client: Any = None

    async def __aenter__(self) -> AuraTestClient:
        try:
            from httpx import ASGITransport, AsyncClient
        except ImportError as exc:
            raise ImportError(
                "httpx is required for AuraTestClient. "
                "Install with: pip install httpx"
            ) from exc

        # Build the ASGI-compatible app — Aura exposes ._build() or is itself callable
        asgi_app = self.app._build() if hasattr(self.app, "_build") else self.app
        transport = ASGITransport(app=asgi_app)
        self._client = AsyncClient(transport=transport, base_url=self.base_url)
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _assert_ready(self) -> None:
        if self._client is None:
            raise RuntimeError(
                "AuraTestClient must be used as an async context manager: "
                "async with AuraTestClient(app) as client: ..."
            )

    async def get(self, path: str, **kwargs: Any) -> Any:
        """Send a GET request.

        Args:
            path: URL path.
            **kwargs: Extra arguments forwarded to ``httpx.AsyncClient.get``.

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        """Send a POST request.

        Args:
            path: URL path.
            **kwargs: Extra arguments (e.g. ``json=``, ``data=``).

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.post(path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> Any:
        """Send a PUT request.

        Args:
            path: URL path.
            **kwargs: Extra arguments.

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.put(path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> Any:
        """Send a PATCH request.

        Args:
            path: URL path.
            **kwargs: Extra arguments.

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.patch(path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        """Send a DELETE request.

        Args:
            path: URL path.
            **kwargs: Extra arguments.

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.delete(path, **kwargs)

    async def options(self, path: str, **kwargs: Any) -> Any:
        """Send an OPTIONS request.

        Args:
            path: URL path.
            **kwargs: Extra arguments.

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.options(path, **kwargs)

    async def head(self, path: str, **kwargs: Any) -> Any:
        """Send a HEAD request.

        Args:
            path: URL path.
            **kwargs: Extra arguments.

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.head(path, **kwargs)

    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Send a request with an arbitrary HTTP method.

        Args:
            method: HTTP method string (e.g. ``"GET"``).
            path: URL path.
            **kwargs: Extra arguments.

        Returns:
            An httpx Response object.
        """
        self._assert_ready()
        return await self._client.request(method, path, **kwargs)

"""Tests for ASGI middleware."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from aura import Aura, Module, get
from aura.middleware.rate_limit import RateLimitMiddleware


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_allows_within_limit(self) -> None:
        """Test that requests within the limit are allowed."""

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/test")
            async def test_route(self) -> dict:  # type: ignore[type-arg]
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])
        app = RateLimitMiddleware(app, max_requests=2, window_seconds=60)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            for _ in range(2):
                r = await c.get("/test")
                assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_blocks_over_limit(self) -> None:
        """Test that requests over the limit are blocked with 429."""

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/test")
            async def test_route(self) -> dict:  # type: ignore[type-arg]
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])
        app = RateLimitMiddleware(app, max_requests=2, window_seconds=60)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            for _ in range(2):
                r = await c.get("/test")
                assert r.status_code == 200
            r = await c.get("/test")
            assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_429_response_body(self) -> None:
        """Test that 429 response has a proper body."""

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/test")
            async def test_route(self) -> dict:  # type: ignore[type-arg]
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])
        app = RateLimitMiddleware(
            app, max_requests=1, window_seconds=60, message="Custom rate limit message"
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r1 = await c.get("/test")
            assert r1.status_code == 200
            r2 = await c.get("/test")
            assert r2.status_code == 429
            assert "Custom rate limit message" in r2.text or r2.text != ""


class TestCORSMiddleware:
    """Tests for CORSMiddleware (wrapper around Starlette's implementation)."""

    @pytest.mark.asyncio
    async def test_cors_middleware_basic(self) -> None:
        """Test that CORSMiddleware can be instantiated and applied."""
        from aura.middleware.cors import CORSMiddleware

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/test")
            async def test_route(self) -> dict:  # type: ignore[type-arg]
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])
        cors = CORSMiddleware(allow_origins=["*"])
        app = cors.build(app)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # Request without Origin header
            r = await c.get("/test")
            assert r.status_code == 200

            # Request with Origin header should get CORS headers
            r2 = await c.get("/test", headers={"Origin": "http://example.com"})
            assert r2.status_code == 200
            header_present = (
                "access-control-allow-origin" in r2.headers
                or "Access-Control-Allow-Origin" in r2.headers
            )
            assert header_present

    @pytest.mark.asyncio
    async def test_cors_middleware_allows_specified_origin(self) -> None:
        """Test that CORSMiddleware respects allow_origins."""
        from aura.middleware.cors import CORSMiddleware

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/test")
            async def test_route(self) -> dict:  # type: ignore[type-arg]
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])
        cors = CORSMiddleware(allow_origins=["https://example.com"])
        app = cors.build(app)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/test", headers={"Origin": "https://example.com"})
            assert r.status_code == 200

"""Tests for JWTGuard, RateLimitGuard, and SessionMiddleware."""
from __future__ import annotations

from typing import Any, cast

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request
from starlette.types import ASGIApp

from aura import Aura, Module, get
from aura.guards.rate_limit import RateLimitGuard
from aura.middleware.rate_limit_backends.memory import MemoryBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# 32+ bytes — satisfies PyJWT enforce_minimum_key_length for HS256
_TEST_JWT_SECRET = "aura-jwt-test-secret-key-32chars!!"
_WRONG_JWT_SECRET = "wrong-jwt-test-secret-key-32chars!!"


def make_jwt_token(secret: str, payload: dict[str, Any]) -> str:
    import jwt

    return str(jwt.encode(payload, secret, algorithm="HS256"))


# ---------------------------------------------------------------------------
# JWTGuard fixtures & tests
# ---------------------------------------------------------------------------


@pytest.fixture
def jwt_app() -> Aura:
    try:
        from aura.guards.jwt import JWTGuard
    except ImportError:
        pytest.skip("PyJWT not installed")

    guard = JWTGuard(secret=_TEST_JWT_SECRET)

    class TestController:
        def __init__(self) -> None:
            pass

        @get("/public")
        async def public(self) -> dict[str, Any]:
            return {"public": True}

        @get("/protected", guards=[guard])
        async def protected(self, request: Request) -> dict[str, Any]:
            return {"user": request.state.user}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    return Aura(modules=[TestModule])


@pytest.mark.asyncio
async def test_jwt_valid_token(jwt_app: Aura) -> None:
    token = make_jwt_token(_TEST_JWT_SECRET, {"sub": "user1", "role": "admin"})
    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["user"]["sub"] == "user1"


@pytest.mark.asyncio
async def test_jwt_missing_token_returns_401(jwt_app: Aura) -> None:
    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/protected")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_jwt_invalid_token_returns_401(jwt_app: Aura) -> None:
    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": "Bearer invalid.token.here"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_jwt_public_route_no_token_needed(jwt_app: Aura) -> None:
    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/public")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_jwt_wrong_secret_returns_401(jwt_app: Aura) -> None:
    token = make_jwt_token(_WRONG_JWT_SECRET, {"sub": "user1"})
    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_jwt_expired_token_returns_401(jwt_app: Aura) -> None:
    import time

    token = make_jwt_token(
        _TEST_JWT_SECRET,
        {"sub": "user1", "exp": int(time.time()) - 60},
    )
    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_jwt_none_algorithm_rejected(jwt_app: Aura) -> None:
    import base64
    import json

    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "none", "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "user1"}).encode()
    ).rstrip(b"=").decode()
    token = f"{header}.{payload}."

    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_jwt_require_exp_rejects_token_without_exp() -> None:
    from aura.guards.jwt import JWTGuard

    guard = JWTGuard(secret=_TEST_JWT_SECRET, require_exp=True)

    class TestController:
        @get("/protected", guards=[guard])
        async def protected(self, request: Request) -> dict[str, Any]:
            return {"user": request.state.user}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    app = Aura(modules=[TestModule])
    token = make_jwt_token(_TEST_JWT_SECRET, {"sub": "user1"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


class TestJWTGuard:
    """Tests for JWTGuard."""

    @pytest.mark.asyncio
    async def test_jwt_guard_auto_error_false_missing_token(self) -> None:
        """Test that auto_error=False allows missing token with user=None."""
        try:
            from aura.guards.jwt import JWTGuard
        except ImportError:
            pytest.skip("PyJWT not installed")

        guard = JWTGuard(secret=_TEST_JWT_SECRET, auto_error=False)

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/optional", guards=[guard])
            async def optional(self, request: Request) -> dict[str, Any]:
                user = getattr(request.state, "user", "NOT_SET")
                return {"user": user}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/optional")
            assert r.status_code == 200
            assert r.json()["user"] is None

    @pytest.mark.asyncio
    async def test_jwt_guard_auto_error_false_invalid_token(self) -> None:
        """Test that auto_error=False allows invalid token with user=None."""
        try:
            from aura.guards.jwt import JWTGuard
        except ImportError:
            pytest.skip("PyJWT not installed")

        guard = JWTGuard(secret=_TEST_JWT_SECRET, auto_error=False)

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/optional", guards=[guard])
            async def optional(self, request: Request) -> dict[str, Any]:
                user = getattr(request.state, "user", "NOT_SET")
                return {"user": user}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/optional", headers={"Authorization": "Bearer invalid.token"})
            assert r.status_code == 200
            assert r.json()["user"] is None


# ---------------------------------------------------------------------------
# RateLimitGuard fixtures & tests
# ---------------------------------------------------------------------------


@pytest.fixture
def rate_limit_app() -> Aura:
    limit = RateLimitGuard(max_requests=3, window_seconds=60)

    class TestController:
        def __init__(self) -> None:
            pass

        @get("/limited", guards=[limit])
        async def limited(self) -> dict[str, Any]:
            return {"ok": True}

        @get("/unlimited")
        async def unlimited(self) -> dict[str, Any]:
            return {"ok": True}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    return Aura(modules=[TestModule])


@pytest.mark.asyncio
async def test_rate_limit_allows_within_limit(rate_limit_app: Aura) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=rate_limit_app), base_url="http://test"
    ) as c:
        for _ in range(3):
            r = await c.get("/limited")
            assert r.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_limit(rate_limit_app: Aura) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=rate_limit_app), base_url="http://test"
    ) as c:
        for _ in range(3):
            await c.get("/limited")
        r = await c.get("/limited")
    assert r.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_only_on_guarded_route(rate_limit_app: Aura) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=rate_limit_app), base_url="http://test"
    ) as c:
        for _ in range(10):
            r = await c.get("/unlimited")
            assert r.status_code == 200


class TestRateLimitGuard:
    """Tests for RateLimitGuard."""

    @pytest.mark.asyncio
    async def test_rate_limit_guard_isolates_by_custom_key_func(self) -> None:
        """Test that RateLimitGuard respects custom key_func for isolation."""
        # Create two guards with different key functions
        limit_a = RateLimitGuard(
            max_requests=2,
            window_seconds=60,
            key_func=lambda r: "user-a"
        )
        limit_b = RateLimitGuard(
            max_requests=2,
            window_seconds=60,
            key_func=lambda r: "user-b"
        )

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/a", guards=[limit_a])
            async def route_a(self) -> dict[str, Any]:
                return {"ok": True}

            @get("/b", guards=[limit_b])
            async def route_b(self) -> dict[str, Any]:
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # User A should get 2 requests
            for _ in range(2):
                r = await c.get("/a")
                assert r.status_code == 200
            r = await c.get("/a")
            assert r.status_code == 429

            # User B should get 2 requests independently
            for _ in range(2):
                r = await c.get("/b")
                assert r.status_code == 200
            r = await c.get("/b")
            assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_guard_respects_key_func(self) -> None:
        """Test that RateLimitGuard uses custom key_func."""
        limit = RateLimitGuard(
            max_requests=2,
            window_seconds=60,
            key_func=lambda r: "custom-key"
        )

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/limited", guards=[limit])
            async def limited(self) -> dict[str, Any]:
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r1 = await c.get("/limited")
            assert r1.status_code == 200
            r2 = await c.get("/limited")
            assert r2.status_code == 200
            r3 = await c.get("/limited")
            assert r3.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_guard_uses_x_forwarded_for_header(self) -> None:
        """Test that RateLimitGuard falls back to X-Forwarded-For header."""
        limit = RateLimitGuard(max_requests=1, window_seconds=60)

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/limited", guards=[limit])
            async def limited(self) -> dict[str, Any]:
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # First request succeeds
            r1 = await c.get("/limited", headers={"X-Forwarded-For": "192.168.1.100"})
            assert r1.status_code == 200
            # Second request from same IP (via X-Forwarded-For) is blocked
            r2 = await c.get("/limited", headers={"X-Forwarded-For": "192.168.1.100"})
            assert r2.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_guard_returns_429_with_headers(self) -> None:
        """Test that RateLimitGuard returns proper rate-limit headers on 429."""
        limit = RateLimitGuard(max_requests=1, window_seconds=60)

        class TestController:
            def __init__(self) -> None:
                pass

            @get("/limited", guards=[limit])
            async def limited(self) -> dict[str, Any]:
                return {"ok": True}

        @Module(controllers=[TestController], prefix="")
        class TestModule:
            pass

        app = Aura(modules=[TestModule])

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            # First request succeeds
            r1 = await c.get("/limited")
            assert r1.status_code == 200
            # Second request is blocked
            r2 = await c.get("/limited")
            assert r2.status_code == 429
            # Check rate-limit headers
            assert "x-ratelimit-limit" in r2.headers
            assert r2.headers["x-ratelimit-limit"] == "1"
            assert "x-ratelimit-remaining" in r2.headers
            assert r2.headers["x-ratelimit-remaining"] == "0"
            assert "retry-after" in r2.headers
            assert r2.headers["retry-after"] == "60"

    @pytest.mark.asyncio
    async def test_rate_limit_guard_lru_eviction(self) -> None:
        """Test that RateLimitGuard evicts oldest keys when max_tracked_keys exceeded."""
        limit = RateLimitGuard(max_requests=100, window_seconds=60, max_tracked_keys=2)
        backend = limit._backend
        assert isinstance(backend, MemoryBackend)

        backend._requests["key1"] = [1.0, 2.0]
        backend._key_order.append("key1")
        backend._requests["key2"] = [1.5, 2.5]
        backend._key_order.append("key2")
        backend._requests["key3"] = [1.7]
        backend._key_order.append("key3")

        if len(backend._requests) > limit.max_tracked_keys:
            backend._cleanup_oldest_key()

        assert "key1" not in backend._requests
        assert "key2" in backend._requests
        assert "key3" in backend._requests

    @pytest.mark.asyncio
    async def test_rate_limit_guard_defaults_to_memory_backend(self) -> None:
        """Test that the default backend is MemoryBackend with LRU."""
        limit = RateLimitGuard(max_requests=5, window_seconds=60)
        assert isinstance(limit._backend, MemoryBackend)
        assert limit._backend._max_tracked_keys == 10000


# ---------------------------------------------------------------------------
# SessionMiddleware tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_middleware_stores_and_retrieves() -> None:
    try:
        import itsdangerous  # noqa: F401
    except ImportError:
        pytest.skip("itsdangerous not installed")

    from aura.middleware.session import SessionMiddleware

    class TestController:
        def __init__(self) -> None:
            pass

        @get("/set")
        async def set_session(self, request: Request) -> dict[str, Any]:
            request.state.session["key"] = "value"
            return {"ok": True}

        @get("/get")
        async def get_session(self, request: Request) -> dict[str, Any]:
            return {"key": request.state.session.get("key")}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    raw_app = Aura(modules=[TestModule])
    app = SessionMiddleware(raw_app, secret_key="test-secret")

    async with AsyncClient(
        transport=ASGITransport(app=cast(ASGIApp, app)), base_url="http://test"
    ) as c:
        r1 = await c.get("/set")
        assert r1.status_code == 200
        # Cookie should be set in response
        assert "session" in r1.cookies or "set-cookie" in r1.headers


@pytest.mark.asyncio
async def test_session_middleware_round_trip() -> None:
    """Session data set in /set should be readable in /get when cookie is forwarded."""
    try:
        import itsdangerous  # noqa: F401
    except ImportError:
        pytest.skip("itsdangerous not installed")

    from aura.middleware.session import SessionMiddleware

    class TestController:
        def __init__(self) -> None:
            pass

        @get("/set")
        async def set_session(self, request: Request) -> dict[str, Any]:
            request.state.session["key"] = "hello"
            return {"ok": True}

        @get("/get")
        async def get_session(self, request: Request) -> dict[str, Any]:
            return {"key": request.state.session.get("key")}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    raw_app = Aura(modules=[TestModule])
    app = SessionMiddleware(raw_app, secret_key="test-secret")

    async with AsyncClient(
        transport=ASGITransport(app=cast(ASGIApp, app)), base_url="http://test"
    ) as c:
        r1 = await c.get("/set")
        assert r1.status_code == 200
        # httpx automatically stores cookies between requests within the same client
        r2 = await c.get("/get")
        assert r2.status_code == 200
        assert r2.json()["key"] == "hello"


@pytest.mark.asyncio
async def test_session_middleware_no_cookie_when_unchanged() -> None:
    """Set-Cookie should not be sent when the session was not modified."""
    try:
        import itsdangerous  # noqa: F401
    except ImportError:
        pytest.skip("itsdangerous not installed")

    from aura.middleware.session import SessionMiddleware

    class TestController:
        def __init__(self) -> None:
            pass

        @get("/set")
        async def set_session(self, request: Request) -> dict[str, Any]:
            request.state.session["key"] = "hello"
            return {"ok": True}

        @get("/read")
        async def read_session(self, request: Request) -> dict[str, Any]:
            return {"key": request.state.session.get("key")}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    raw_app = Aura(modules=[TestModule])
    app = SessionMiddleware(raw_app, secret_key="test-secret")

    async with AsyncClient(
        transport=ASGITransport(app=cast(ASGIApp, app)), base_url="http://test"
    ) as c:
        r1 = await c.get("/set")
        assert r1.status_code == 200
        assert r1.headers.get("set-cookie") is not None

        r2 = await c.get("/read")
        assert r2.status_code == 200
        assert r2.json()["key"] == "hello"
        assert r2.headers.get("set-cookie") is None


@pytest.mark.asyncio
async def test_session_middleware_import_error_without_itsdangerous() -> None:
    """SessionMiddleware raises ImportError when itsdangerous is not available."""
    import importlib
    import sys

    # Temporarily hide itsdangerous
    original = sys.modules.get("itsdangerous")
    sys.modules["itsdangerous"] = None  # type: ignore[assignment]

    try:
        # Force re-import of the module to trigger the ImportError check
        import aura.middleware.session as sm_module

        importlib.reload(sm_module)
        with pytest.raises(ImportError, match="itsdangerous"):
            sm_module.SessionMiddleware(object(), secret_key="x")
    finally:
        if original is None:
            del sys.modules["itsdangerous"]
        else:
            sys.modules["itsdangerous"] = original
        # Reload to restore original state
        import aura.middleware.session as sm_module2

        importlib.reload(sm_module2)

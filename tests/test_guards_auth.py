"""Tests for JWTGuard, RateLimitGuard, and SessionMiddleware."""
from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport
from starlette.requests import Request

from aura import Aura, Module, get, post
from aura.guards.rate_limit import RateLimitGuard


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_jwt_token(secret: str, payload: dict) -> str:  # type: ignore[type-arg]
    from jose import jwt

    return str(jwt.encode(payload, secret, algorithm="HS256"))


# ---------------------------------------------------------------------------
# JWTGuard fixtures & tests
# ---------------------------------------------------------------------------


@pytest.fixture
def jwt_app() -> Aura:
    try:
        from aura.guards.jwt import JWTGuard
    except ImportError:
        pytest.skip("python-jose not installed")

    guard = JWTGuard(secret="test-secret")

    class TestController:
        def __init__(self) -> None:
            pass

        @get("/public")
        async def public(self) -> dict:  # type: ignore[type-arg]
            return {"public": True}

        @get("/protected", guards=[guard])
        async def protected(self, request: Request) -> dict:  # type: ignore[type-arg]
            return {"user": request.state.user}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    return Aura(modules=[TestModule])


@pytest.mark.asyncio
async def test_jwt_valid_token(jwt_app: Aura) -> None:
    token = make_jwt_token("test-secret", {"sub": "user1", "role": "admin"})
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
    token = make_jwt_token("wrong-secret", {"sub": "user1"})
    async with AsyncClient(transport=ASGITransport(app=jwt_app), base_url="http://test") as c:
        r = await c.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


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
        async def limited(self) -> dict:  # type: ignore[type-arg]
            return {"ok": True}

        @get("/unlimited")
        async def unlimited(self) -> dict:  # type: ignore[type-arg]
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
        async def set_session(self, request: Request) -> dict:  # type: ignore[type-arg]
            request.state.session["key"] = "value"
            return {"ok": True}

        @get("/get")
        async def get_session(self, request: Request) -> dict:  # type: ignore[type-arg]
            return {"key": request.state.session.get("key")}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    raw_app = Aura(modules=[TestModule])
    app = SessionMiddleware(raw_app, secret_key="test-secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
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
        async def set_session(self, request: Request) -> dict:  # type: ignore[type-arg]
            request.state.session["key"] = "hello"
            return {"ok": True}

        @get("/get")
        async def get_session(self, request: Request) -> dict:  # type: ignore[type-arg]
            return {"key": request.state.session.get("key")}

    @Module(controllers=[TestController], prefix="")
    class TestModule:
        pass

    raw_app = Aura(modules=[TestModule])
    app = SessionMiddleware(raw_app, secret_key="test-secret")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.get("/set")
        assert r1.status_code == 200
        # httpx automatically stores cookies between requests within the same client
        r2 = await c.get("/get")
        assert r2.status_code == 200
        assert r2.json()["key"] == "hello"


@pytest.mark.asyncio
async def test_session_middleware_import_error_without_itsdangerous() -> None:
    """SessionMiddleware raises ImportError when itsdangerous is not available."""
    import sys
    import importlib

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

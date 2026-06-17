"""Tests for aura.routing module."""

from __future__ import annotations

from typing import Annotated, Any, cast

import pytest

from aura.di.decorators import injectable
from aura.routing.decorators import delete, get, post, ws
from aura.routing.params import (
    Body,
    BodyMarker,
    CookieMarker,
    HeaderMarker,
    Param,
    ParamMarker,
    Query,
    QueryMarker,
)
from aura.routing.router import Router
from aura.schema.base import Schema

# ---------------------------------------------------------------------------
# Decorator tests
# ---------------------------------------------------------------------------


def test_get_decorator_attaches_metadata() -> None:
    @get("/users")
    async def list_users() -> None:
        pass

    assert hasattr(list_users, "__aura_route__")
    meta = cast(Any, list_users).__aura_route__
    assert meta["method"] == "GET"
    assert meta["path"] == "/users"
    assert meta["status"] == 200


def test_post_decorator_default_status_201() -> None:
    @post("/users")
    async def create_user() -> None:
        pass

    assert cast(Any, create_user).__aura_route__["status"] == 201


def test_delete_decorator_default_status_204() -> None:
    @delete("/users/{id}")
    async def delete_user() -> None:
        pass

    assert cast(Any, delete_user).__aura_route__["status"] == 204


def test_decorator_tags_and_summary() -> None:
    @get("/health", tags=["system"], summary="Health check")
    async def health() -> None:
        pass

    meta = cast(Any, health).__aura_route__
    assert meta["tags"] == ["system"]
    assert meta["summary"] == "Health check"


def test_ws_decorator() -> None:
    @ws("/ws/chat")
    async def chat() -> None:
        pass

    assert cast(Any, chat).__aura_route__["method"] == "WS"
    assert cast(Any, chat).__aura_route__["path"] == "/ws/chat"


def test_deprecated_flag() -> None:
    @get("/old-endpoint", deprecated=True)
    async def old_endpoint() -> None:
        pass

    assert cast(Any, old_endpoint).__aura_route__["deprecated"] is True


# ---------------------------------------------------------------------------
# Params marker tests
# ---------------------------------------------------------------------------


def test_body_marker_instance() -> None:
    marker = BodyMarker()
    assert marker.alias is None
    assert marker.embed is False


def test_query_marker_with_alias() -> None:
    marker = QueryMarker(alias="page_num")
    assert marker.alias == "page_num"


def test_param_marker_instance() -> None:
    marker = ParamMarker()
    assert marker.alias is None


def test_header_marker_convert_underscores() -> None:
    marker = HeaderMarker(convert_underscores=True)
    assert marker.convert_underscores is True


def test_cookie_marker_instance() -> None:
    marker = CookieMarker(alias="session")
    assert marker.alias == "session"


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------


def test_router_prefix() -> None:
    router = Router(prefix="/api/v1")
    assert router.prefix == "/api/v1"


def test_router_strips_trailing_slash() -> None:
    router = Router(prefix="/api/v1/")
    assert router.prefix == "/api/v1"


def test_router_include_controller_builds_routes() -> None:
    class UserController:
        @get("/users")
        async def list_users(self) -> None:
            pass

        @post("/users")
        async def create_user(self) -> None:
            pass

    router = Router(prefix="/api")
    router.include_controller(UserController)

    routes = router.build_routes()
    paths = {str(r.path) for r in routes}

    assert "/api/users" in paths
    assert len(routes) == 2


def test_router_add_handler_without_decorator_raises() -> None:
    router = Router()

    async def plain_function() -> None:
        pass

    with pytest.raises(ValueError, match="__aura_route__"):
        router.add_handler(plain_function)


@injectable()
class DummyService:
    def get_value(self) -> str:
        return "injected"


class DiController:
    def __init__(self, service: DummyService) -> None:
        self.service = service

    @get("/hello")
    async def hello(self) -> str:
        return self.service.get_value()


def test_router_controller_with_di() -> None:
    from starlette.testclient import TestClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(
        providers=[DummyService],
        controllers=[DiController],
    )
    class DiModule:
        pass

    app = Aura(modules=[DiModule])
    client = TestClient(app)
    response = client.get("/hello")
    assert response.status_code == 200
    assert response.json() == "injected"


# ---------------------------------------------------------------------------
# Integration tests with HTTP errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_raising_runtime_error_returns_500() -> None:
    """Test that an unhandled RuntimeError in a handler returns HTTP 500."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    class ErrorController:
        @get("/error")
        async def error(self) -> None:
            raise RuntimeError("unexpected error")

    @Module(controllers=[ErrorController], prefix="")
    class ErrorModule:
        pass

    app = Aura(modules=[ErrorModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/error")
        assert r.status_code == 500


# ---------------------------------------------------------------------------
# Param binding integration tests — shared fixtures at module level
# ---------------------------------------------------------------------------

# Schema for Body binding tests
class UserSchema(Schema):
    name: str
    email: str


# Controller for Body binding tests
class UserBodyController:
    @post("/users")
    async def create_user(self, body: Body[UserSchema]) -> UserSchema:  # type: ignore[valid-type]
        # Echo back the created user
        return body


# Controller for Query binding tests
class ListQueryController:
    @get("/items")
    async def list_items(self, page: Query[int]) -> dict[str, int]:  # type: ignore[valid-type]
        return {"page": page}


# Controller for required Query binding tests
class SearchQueryController:
    @get("/search")
    async def search(
        self, q: Annotated[str, QueryMarker(required=True)]
    ) -> dict[str, str]:
        return {"q": q}


# Controller for path param binding tests
class ItemPathController:
    @get("/items/{item_id}")
    async def get_item(self, item_id: Param[int]) -> dict[str, int]:  # type: ignore[valid-type]
        return {"item_id": item_id}


# Controller for header binding tests
class SecureHeaderController:
    @get("/secure")
    async def secure_endpoint(
        self, x_token: Annotated[str, HeaderMarker()]
    ) -> dict[str, str]:
        return {"token": x_token}


# Controller for cookie binding tests
class ProfileCookieController:
    @get("/profile")
    async def get_profile(
        self, session: Annotated[str, CookieMarker()]
    ) -> dict[str, str]:
        return {"session": session}


@pytest.mark.asyncio
async def test_body_binding() -> None:
    """Test that Body marker correctly injects Pydantic models from JSON request body."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[UserBodyController], prefix="")
    class UserModule:
        pass

    app = Aura(modules=[UserModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/users",
            json={"name": "Alice", "email": "alice@example.com"}
        )
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_query_param_binding() -> None:
    """Test that Query marker correctly extracts and coerces query parameters."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[ListQueryController], prefix="")
    class ListModule:
        pass

    app = Aura(modules=[ListModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/items?page=3")
        assert r.status_code == 200
        data = r.json()
        assert data["page"] == 3


@pytest.mark.asyncio
async def test_query_param_missing_required_returns_422() -> None:
    """Test that missing required query parameter returns HTTP 422."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[SearchQueryController], prefix="")
    class SearchModule:
        pass

    app = Aura(modules=[SearchModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/search")
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_implicit_path_param_binding() -> None:
    """Test that path parameters are automatically bound and coerced."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[ItemPathController], prefix="")
    class ItemModule:
        pass

    app = Aura(modules=[ItemModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/items/42")
        assert r.status_code == 200
        data = r.json()
        assert data["item_id"] == 42


@pytest.mark.asyncio
async def test_header_binding() -> None:
    """Test that Header marker correctly extracts request headers."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[SecureHeaderController], prefix="")
    class SecureModule:
        pass

    app = Aura(modules=[SecureModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/secure", headers={"X-Token": "secret123"})
        assert r.status_code == 200
        data = r.json()
        assert data["token"] == "secret123"


@pytest.mark.asyncio
async def test_cookie_binding() -> None:
    """Test that Cookie marker correctly extracts request cookies."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[ProfileCookieController], prefix="")
    class ProfileModule:
        pass

    app = Aura(modules=[ProfileModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/profile", cookies={"session": "abc"})
        assert r.status_code == 200
        data = r.json()
        assert data["session"] == "abc"


# ---------------------------------------------------------------------------
# Security: invalid coercion, empty body, invalid JSON, missing required params
# ---------------------------------------------------------------------------


class CoercionErrorController:
    @get("/items")
    async def list_items(self, page: Query[int]) -> dict[str, int]:  # type: ignore[valid-type]
        return {"page": page}


@pytest.mark.asyncio
async def test_invalid_query_int_coercion_returns_422() -> None:
    """Test that invalid query int coercion returns HTTP 422."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[CoercionErrorController], prefix="")
    class CoercionModule:
        pass

    app = Aura(modules=[CoercionModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/items?page=invalid_int")
        assert r.status_code == 422
        data = r.json()
        assert "error" in data


class RequiredBodyController:
    @post("/data")
    async def create_data(self, body: Body[UserSchema]) -> UserSchema:  # type: ignore[valid-type]
        return body


@pytest.mark.asyncio
async def test_empty_required_body_returns_422() -> None:
    """Test that empty required body returns HTTP 422."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[RequiredBodyController], prefix="")
    class RequiredBodyModule:
        pass

    app = Aura(modules=[RequiredBodyModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/data", content="")
        assert r.status_code == 422
        data = r.json()
        assert "error" in data


@pytest.mark.asyncio
async def test_invalid_json_body_returns_422() -> None:
    """Test that invalid JSON body returns HTTP 422."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[RequiredBodyController], prefix="")
    class RequiredBodyModule2:
        pass

    app = Aura(modules=[RequiredBodyModule2])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/data",
            content="{invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422
        data = r.json()
        assert "error" in data


class RequiredHeaderController:
    @get("/secure-header")
    async def secure_endpoint(
        self, x_token: Annotated[str, HeaderMarker(required=True)]
    ) -> dict[str, str]:
        return {"token": x_token}


@pytest.mark.asyncio
async def test_missing_required_header_returns_422() -> None:
    """Test that missing required header returns HTTP 422."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[RequiredHeaderController], prefix="")
    class RequiredHeaderModule:
        pass

    app = Aura(modules=[RequiredHeaderModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/secure-header")
        assert r.status_code == 422
        data = r.json()
        assert "error" in data


class RequiredCookieController:
    @get("/profile-secure")
    async def get_profile(
        self, session: Annotated[str, CookieMarker(required=True)]
    ) -> dict[str, str]:
        return {"session": session}


@pytest.mark.asyncio
async def test_missing_required_cookie_returns_422() -> None:
    """Test that missing required cookie returns HTTP 422."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module

    @Module(controllers=[RequiredCookieController], prefix="")
    class RequiredCookieModule:
        pass

    app = Aura(modules=[RequiredCookieModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/profile-secure")
        assert r.status_code == 422
        data = r.json()
        assert "error" in data
    """Test that response schemas automatically serialize ORM-like objects at C-speed."""
    from httpx import ASGITransport, AsyncClient

    from aura.core.app import Aura
    from aura.modules.base import Module
    from aura.orm.repository import Page
    from aura.schema.base import Schema

    class MockUser:
        def __init__(self, id: int, name: str) -> None:
            self.id = id
            self.name = name

    class UserResponse(Schema):
        id: int
        name: str

    class SerializationController:
        @get("/users", response=list[UserResponse])
        async def list_users(self) -> list[MockUser]:
            # Return raw ORM-like objects, they will be serialized at Rust speed!
            return [MockUser(1, "Alice"), MockUser(2, "Bob")]

        @get("/users/paginated", response=Page[UserResponse])
        async def paginate_users(self) -> Page[MockUser]:
            return Page(
                items=[MockUser(1, "Alice"), MockUser(2, "Bob")],
                total=2,
                page=1,
                per_page=10,
                has_next=False,
            )

    @Module(controllers=[SerializationController], prefix="")
    class SerializationModule:
        pass

    app = Aura(modules=[SerializationModule])

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        # Test List serialization
        r1 = await c.get("/users")
        assert r1.status_code == 200
        data1 = r1.json()
        assert len(data1) == 2
        assert data1[0]["id"] == 1
        assert data1[0]["name"] == "Alice"

        # Test Page serialization
        r2 = await c.get("/users/paginated")
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["total"] == 2
        assert len(data2["items"]) == 2
        assert data2["items"][0]["name"] == "Alice"

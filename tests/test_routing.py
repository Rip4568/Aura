"""Tests for aura.routing module."""

from __future__ import annotations

import pytest

from aura.routing.decorators import delete, get, post, ws
from aura.routing.params import (
    BodyMarker,
    CookieMarker,
    HeaderMarker,
    ParamMarker,
    QueryMarker,
)
from aura.routing.router import Router

# ---------------------------------------------------------------------------
# Decorator tests
# ---------------------------------------------------------------------------


def test_get_decorator_attaches_metadata() -> None:
    @get("/users")
    async def list_users() -> None:
        pass

    assert hasattr(list_users, "__aura_route__")
    meta = list_users.__aura_route__
    assert meta["method"] == "GET"
    assert meta["path"] == "/users"
    assert meta["status"] == 200


def test_post_decorator_default_status_201() -> None:
    @post("/users")
    async def create_user() -> None:
        pass

    assert create_user.__aura_route__["status"] == 201


def test_delete_decorator_default_status_204() -> None:
    @delete("/users/{id}")
    async def delete_user() -> None:
        pass

    assert delete_user.__aura_route__["status"] == 204


def test_decorator_tags_and_summary() -> None:
    @get("/health", tags=["system"], summary="Health check")
    async def health() -> None:
        pass

    meta = health.__aura_route__
    assert meta["tags"] == ["system"]
    assert meta["summary"] == "Health check"


def test_ws_decorator() -> None:
    @ws("/ws/chat")
    async def chat() -> None:
        pass

    assert chat.__aura_route__["method"] == "WS"
    assert chat.__aura_route__["path"] == "/ws/chat"


def test_deprecated_flag() -> None:
    @get("/old-endpoint", deprecated=True)
    async def old_endpoint() -> None:
        pass

    assert old_endpoint.__aura_route__["deprecated"] is True


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

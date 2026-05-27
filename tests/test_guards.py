"""Tests for aura.guards module."""

from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from aura.exceptions.http import ForbiddenException
from aura.guards.base import Guard


# ---------------------------------------------------------------------------
# Guard implementations for testing
# ---------------------------------------------------------------------------


class AllowAllGuard(Guard):
    """Guard that always allows requests."""

    async def can_activate(self, request: Request) -> bool:
        return True


class DenyAllGuard(Guard):
    """Guard that always denies requests."""

    async def can_activate(self, request: Request) -> bool:
        return False


class HeaderGuard(Guard):
    """Guard that requires a specific header value."""

    def __init__(self, header: str, expected: str) -> None:
        self.header = header
        self.expected = expected

    async def can_activate(self, request: Request) -> bool:
        return request.headers.get(self.header) == self.expected


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allow_all_guard_returns_true() -> None:
    guard = AllowAllGuard()
    # Create a minimal mock request
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    assert await guard.can_activate(request) is True


@pytest.mark.asyncio
async def test_deny_all_guard_returns_false() -> None:
    guard = DenyAllGuard()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    assert await guard.can_activate(request) is False


@pytest.mark.asyncio
async def test_on_denied_raises_forbidden() -> None:
    guard = DenyAllGuard()
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    with pytest.raises(ForbiddenException):
        await guard.on_denied(request)


@pytest.mark.asyncio
async def test_header_guard_allows_matching_header() -> None:
    guard = HeaderGuard("X-API-Key", "secret")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-api-key", b"secret")],
        "query_string": b"",
    }
    request = Request(scope)
    assert await guard.can_activate(request) is True


@pytest.mark.asyncio
async def test_header_guard_denies_wrong_header() -> None:
    guard = HeaderGuard("X-API-Key", "secret")
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(b"x-api-key", b"wrong")],
        "query_string": b"",
    }
    request = Request(scope)
    assert await guard.can_activate(request) is False

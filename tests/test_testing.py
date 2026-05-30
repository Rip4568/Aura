"""Tests for the public testing module (aura.testing)."""

from __future__ import annotations

import pytest

from aura import Aura, Module, delete, get, patch, post, put
from aura.routing.decorators import _route_decorator
from aura.testing.client import AuraTestClient
from aura.testing.fixtures import aura_app, test_client  # noqa: F401


class TestController:
    """Controller for testing AuraTestClient capabilities."""

    @get("/test")
    async def handle_get(self) -> dict:
        return {"method": "GET"}

    @post("/test")
    async def handle_post(self) -> dict:
        return {"method": "POST"}

    @put("/test")
    async def handle_put(self) -> dict:
        return {"method": "PUT"}

    @patch("/test")
    async def handle_patch(self) -> dict:
        return {"method": "PATCH"}

    @delete("/test")
    async def handle_delete(self) -> dict:
        return {"method": "DELETE"}

    @_route_decorator("OPTIONS", "/test")
    async def handle_options(self) -> dict:
        return {"method": "OPTIONS"}



@Module(controllers=[TestController])
class TestModule:
    pass


# Simple app with multiple verbs for testing client capabilities
app = Aura(modules=[TestModule], title="Test App")


class TestAuraTestClient:
    """Suite of tests covering the public AuraTestClient utility."""

    async def test_client_requires_context_manager(self) -> None:
        """Verifies that calling methods without enters raises a RuntimeError."""
        client = AuraTestClient(app)
        with pytest.raises(RuntimeError) as exc_info:
            await client.get("/test")
        assert "must be used as an async context manager" in str(exc_info.value)

    async def test_http_verbs_and_request(self) -> None:
        """Verifies all HTTP verb wrapper methods in AuraTestClient."""
        async with AuraTestClient(app) as client:
            # Test GET
            resp = await client.get("/test")
            assert resp.status_code == 200
            assert resp.json() == {"method": "GET"}

            # Test POST
            resp = await client.post("/test")
            assert resp.status_code == 201
            assert resp.json() == {"method": "POST"}

            # Test PUT
            resp = await client.put("/test")
            assert resp.status_code == 200
            assert resp.json() == {"method": "PUT"}

            # Test PATCH
            resp = await client.patch("/test")
            assert resp.status_code == 200
            assert resp.json() == {"method": "PATCH"}

            # Test DELETE
            resp = await client.delete("/test")
            assert resp.status_code == 204

            # Test generic request options/head
            resp = await client.options("/test")
            assert resp.status_code == 200

            resp = await client.head("/test")
            assert resp.status_code == 200

            # Test arbitrary request method
            resp = await client.request("GET", "/test")
            assert resp.status_code == 200
            assert resp.json() == {"method": "GET"}


@pytest.mark.anyio
async def test_client_fixture_integration(test_client: AuraTestClient) -> None:  # noqa: F811
    """Verifies that the public test_client fixture is properly wired and ready."""
    # Note: the default fixture yields Aura() which has no custom routes, but we can verify it boots
    resp = await test_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


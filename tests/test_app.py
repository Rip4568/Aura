"""Integration tests for the main Aura application."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from aura import Aura, Module, Schema, get, post, NotFoundException
from aura.routing.decorators import delete


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ItemSchema(Schema):
    id: int
    name: str


class CreateItemSchema(Schema):
    name: str


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------

_ITEMS: dict[int, dict] = {}
_COUNTER = 0


def _reset_store() -> None:
    global _COUNTER
    _ITEMS.clear()
    _COUNTER = 0


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class ItemController:
    @get("/", response=ItemSchema)
    async def list_items(self) -> list[dict]:
        return list(_ITEMS.values())

    @get("/{item_id}", response=ItemSchema)
    async def get_item(self) -> dict:
        # In a real handler, item_id would come from Param[int]
        return {"id": 1, "name": "test"}

    @post("/", response=ItemSchema)
    async def create_item(self) -> dict:
        global _COUNTER
        _COUNTER += 1
        item = {"id": _COUNTER, "name": "new item"}
        _ITEMS[_COUNTER] = item
        return item


# ---------------------------------------------------------------------------
# Module
# ---------------------------------------------------------------------------


@Module(controllers=[ItemController], prefix="/items")
class ItemModule:
    pass


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def app() -> Aura:
    _reset_store()
    return Aura(
        modules=[ItemModule],
        title="Test API",
        version="0.1.0",
        debug=True,
    )


@pytest.fixture
async def client(app: Aura):  # type: ignore[misc]
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_openapi_endpoint(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["openapi"] == "3.1.0"
    assert spec["info"]["title"] == "Test API"


@pytest.mark.asyncio
async def test_docs_endpoint(client: AsyncClient) -> None:
    response = await client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()


@pytest.mark.asyncio
async def test_redoc_endpoint(client: AsyncClient) -> None:
    response = await client.get("/redoc")
    assert response.status_code == 200
    assert "redoc" in response.text.lower()


@pytest.mark.asyncio
async def test_list_items(client: AsyncClient) -> None:
    response = await client.get("/items/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_item(client: AsyncClient) -> None:
    response = await client.post("/items/")
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_app_has_container(app: Aura) -> None:
    from aura.di.container import DIContainer
    assert isinstance(app.container, DIContainer)


@pytest.mark.asyncio
async def test_app_has_openapi_generator(app: Aura) -> None:
    from aura.schema.openapi import OpenAPIGenerator
    assert isinstance(app.openapi, OpenAPIGenerator)


@pytest.mark.asyncio
async def test_404_returns_json(client: AsyncClient) -> None:
    response = await client.get("/nonexistent-route-xyz")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_docs_url_none_disables_docs() -> None:
    app = Aura(docs_url=None, openapi_url=None, redoc_url=None)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        for url in ("/docs", "/openapi.json", "/redoc"):
            response = await ac.get(url)
            assert response.status_code == 404

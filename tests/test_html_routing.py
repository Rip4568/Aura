"""Integration tests for @html and @sse route decorators.

These tests exercise the router's HTML/SSE rendering path without Jinja2
(handlers return plain strings or already-rendered HtmlResponse objects).
No template engine setup is required.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from aura import Aura, Module, get
from aura.core.request import AuraRequest
from aura.templates.decorators import html, sse
from aura.templates.response import HtmlResponse

# ---------------------------------------------------------------------------
# Controllers
# ---------------------------------------------------------------------------

class HomeController:
    """Stateless controller — no DI dependencies."""

    @html("/")
    async def index(self) -> str:
        return "<h1>Welcome to Aura</h1>"

    @html("/raw")
    async def raw_response(self) -> HtmlResponse:
        """Handler that builds and returns HtmlResponse directly."""
        return HtmlResponse("<b>raw</b>", status_code=200)

    @html("/created", status=201)
    async def created(self) -> str:
        return "<p>created</p>"


class EventController:
    """SSE endpoints."""

    @sse("/stream")
    async def stream(self) -> AsyncIterator[dict[str, object]]:
        yield {"event": "ping", "count": 1}
        yield {"event": "pong", "count": 2}

    @sse("/text-stream")
    async def text_stream(self) -> AsyncIterator[str]:
        yield "hello"
        yield "world"


class RequestInspectController:
    """Verify AuraRequest is injected when typed as parameter."""

    @html("/req-check")
    async def check_request(self, request: AuraRequest) -> str:
        return f"<p>method={request.method}</p>"

    @get("/req-json")
    async def check_request_json(self, request: AuraRequest) -> dict:
        return {"method": request.method}


# ---------------------------------------------------------------------------
# Modules & fixtures
# ---------------------------------------------------------------------------

@Module(
    controllers=[HomeController, EventController, RequestInspectController],
    prefix="/html-test",
)
class HtmlTestModule:
    pass


@pytest.fixture
async def html_client() -> AsyncClient:
    app = Aura(modules=[HtmlTestModule], title="HTML Test")
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# @html: plain string return
# ---------------------------------------------------------------------------

async def test_html_route_returns_html_content_type(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


async def test_html_route_body(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/")
    assert "Welcome to Aura" in r.text


async def test_html_route_custom_status(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/created")
    assert r.status_code == 201
    assert "created" in r.text


async def test_html_route_raw_response_passthrough(html_client: AsyncClient) -> None:
    """Handler returning HtmlResponse directly should be passed through unchanged."""
    r = await html_client.get("/html-test/raw")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<b>raw</b>" in r.text


# ---------------------------------------------------------------------------
# @sse: streaming
# ---------------------------------------------------------------------------

async def test_sse_route_content_type(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/stream")
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


async def test_sse_route_sends_json_events(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/stream")
    body = r.text
    assert "data:" in body
    assert "ping" in body
    assert "pong" in body


async def test_sse_text_stream(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/text-stream")
    body = r.text
    assert "data: hello" in body
    assert "data: world" in body


# ---------------------------------------------------------------------------
# AuraRequest injection
# ---------------------------------------------------------------------------

async def test_aura_request_injected_in_html_route(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/req-check")
    assert r.status_code == 200
    assert "method=GET" in r.text


async def test_aura_request_injected_in_json_route(html_client: AsyncClient) -> None:
    r = await html_client.get("/html-test/req-json")
    assert r.status_code == 200
    data = r.json()
    assert data["method"] == "GET"

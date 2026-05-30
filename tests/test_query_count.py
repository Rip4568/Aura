"""Tests for QueryCountMiddleware and SQL profiling features."""

from __future__ import annotations

import pytest

from aura import Aura, get
from aura.middleware.query_count import QueryCountMiddleware
from aura.orm.profiling import query_log, log_query, setup_query_profiling
from aura.testing.client import AuraTestClient


# Helper controller to simulate queries
@get("/no-queries")
async def no_queries() -> dict:
    return {"ok": True}


@get("/simulate-queries")
async def simulate_queries() -> dict:
    # Programmatically log SQL queries inside the request scope
    log_query("SELECT * FROM users WHERE id = 1", 0.5)
    log_query("SELECT * FROM users WHERE id = 2", 0.3)
    return {"ok": True}


@get("/simulate-n1-risk")
async def simulate_n1_risk() -> dict:
    # Log identical queries to trigger N+1 detection
    log_query("SELECT * FROM posts WHERE user_id = ?", 1.2)
    log_query("SELECT * FROM posts WHERE user_id = ?", 0.8)
    return {"ok": True}


class TestQueryCountMiddleware:
    """Suite of tests covering the QueryCountMiddleware."""

    async def test_disabled_by_default_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that the middleware does not inject headers when only_debug=True and AURA__DEBUG=False."""
        monkeypatch.setenv("AURA__DEBUG", "false")
        app = Aura(title="Production App")
        app.add_middleware(QueryCountMiddleware)
        app.router.add_route(no_queries)

        async with AuraTestClient(app) as client:
            resp = await client.get("/no-queries")
            assert resp.status_code == 200
            assert "x-query-count" not in resp.headers
            assert "x-query-time-ms" not in resp.headers

    async def test_always_on_when_only_debug_is_false(self) -> None:
        """Verifies that the middleware is active when only_debug=False even if AURA__DEBUG=False."""
        app = Aura(title="Monitoring App")
        app.add_middleware(QueryCountMiddleware, only_debug=False)
        app.router.add_route(simulate_queries)

        async with AuraTestClient(app) as client:
            resp = await client.get("/simulate-queries")
            assert resp.status_code == 200
            assert resp.headers["x-query-count"] == "2"
            assert "x-query-time-ms" in resp.headers

    async def test_active_in_debug_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifies that the middleware injects headers when AURA__DEBUG=true."""
        monkeypatch.setenv("AURA__DEBUG", "true")
        app = Aura(title="Debug App")
        app.add_middleware(QueryCountMiddleware)
        app.router.add_route(simulate_queries)

        async with AuraTestClient(app) as client:
            resp = await client.get("/simulate-queries")
            assert resp.status_code == 200
            assert resp.headers["x-query-count"] == "2"
            assert float(resp.headers["x-query-time-ms"]) == 0.8

    async def test_n1_risk_detection(self) -> None:
        """Verifies that duplicate SQL patterns generate the x-query-n1-risk header."""
        app = Aura(title="N1 App")
        app.add_middleware(QueryCountMiddleware, only_debug=False)
        app.router.add_route(simulate_n1_risk)

        async with AuraTestClient(app) as client:
            resp = await client.get("/simulate-n1-risk")
            assert resp.status_code == 200
            assert resp.headers["x-query-count"] == "2"
            assert resp.headers["x-query-n1-risk"] == "1"

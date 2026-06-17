"""Request-scoped Dependency Injection container middleware for Aura."""

from __future__ import annotations

import logging
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("aura.middleware.di")


class DIRequestScopeMiddleware:
    """Middleware that creates a scoped child container for every HTTP or
    WebSocket request.

    The request-scoped container shares the global singleton providers but
    maintains its own isolated cache for request-scoped dependencies.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Fetch global container from Starlette application state
        app = scope.get("app")
        global_container = getattr(getattr(app, "state", None), "container", None)

        scoped_container: Any | None = None
        try:
            if global_container is not None:
                scoped_container = global_container.create_scope()
                scope.setdefault("state", {})["container"] = scoped_container
                logger.debug("Initialized request-scoped DI container.")

            await self.app(scope, receive, send)
        finally:
            if scoped_container is not None:
                scoped_container.clear_scope_cache()

"""Request processing pipeline for the Aura framework."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("aura.pipeline")

MiddlewareCallable = Callable[[Any, Any], Any]


class RequestPipeline:
    """
    Builds and manages the ASGI middleware pipeline.

    The pipeline wraps an inner ASGI application with a stack of middleware
    callables.  Middleware is applied in the order it appears in the list —
    the first item in the list is the outermost (first to receive the request,
    last to send the response).

    Args:
        app: The inner ASGI application (typically the Starlette router).
        middleware: Ordered list of middleware to apply.
    """

    def __init__(
        self,
        app: ASGIApp,
        middleware: list[Any] | None = None,
    ) -> None:
        self._app = app
        self._middleware = list(middleware or [])
        self._built: ASGIApp | None = None

    def build(self) -> ASGIApp:
        """Compose all middleware into a single ASGI callable.

        Returns:
            The outermost ASGI application after wrapping with all middleware.
        """
        app: ASGIApp = self._app
        for mw in reversed(self._middleware):
            if callable(mw):
                app = mw(app)
            elif hasattr(mw, "cls"):
                # Starlette ``Middleware(cls, **kwargs)`` descriptor
                app = mw.cls(app, **mw.kwargs)
            else:
                logger.warning("Unrecognised middleware: %r — skipping", mw)
        self._built = app
        return app

    @property
    def built_app(self) -> ASGIApp | None:
        """Return the composed ASGI app, or ``None`` if :meth:`build` has not been called."""
        return self._built

    def add_middleware(self, middleware: Any) -> None:
        """Append a middleware to the pipeline.

        .. note::
            This must be called **before** :meth:`build` to take effect.

        Args:
            middleware: A middleware callable or Starlette ``Middleware`` descriptor.
        """
        self._middleware.append(middleware)
        self._built = None  # invalidate built pipeline


class LoggingMiddleware:
    """
    Simple request/response logging middleware.

    Logs the HTTP method, URL path, status code, and elapsed time for every
    request.

    Args:
        app: The inner ASGI application.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time

        method = scope.get("method", "")
        path = scope.get("path", "")
        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Any) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "%s %s → %d (%.1f ms)", method, path, status_code, elapsed_ms
            )

"""Logging interceptor — structured request/response logging."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aura.interceptors.base import Interceptor
from aura.logging.constants import DEFAULT_SENSITIVE_FIELDS
from aura.logging.context import get_current_context
from aura.logging.sanitizer import Sanitizer

logger = logging.getLogger("aura.access")


class ChainRequestLogInterceptor(Interceptor):
    """Logs every request with method, path, status code, elapsed time, and context.

    Automatically includes structured fields in JSON logs: method, path, status_code,
    elapsed_ms, request_id, and user_id (from context variables).

    Output goes to the ``aura.access`` logger at INFO level.

    Log format (plain)::

        GET /users/ 200 12.3ms

    Log format (JSON)::

        {
            "timestamp": "2026-05-29 10:30:45",
            "level": "INFO",
            "logger": "aura.access",
            "message": "GET /users/ 200 12.3ms",
            "method": "GET",
            "path": "/users/",
            "status_code": 200,
            "elapsed_ms": 12.3,
            "request_id": "abc123",
            "user_id": 42
        }

    Args:
        log_headers: If ``True``, request headers are also logged at DEBUG level.
        log_body: If ``True``, the request body is logged at DEBUG level
                  (only safe for small payloads).

    Note:
        This interceptor uses the :class:`Interceptor` chain protocol and is
        wired via ``Aura(interceptors=[...])``.  For an ASGI middleware that
        integrates directly with ``Aura(middleware=...)``, use
        :class:`aura.logging.interceptor.RequestLogInterceptor` instead::

            from starlette.middleware import Middleware
            from aura import Aura
            from aura.logging import RequestLogInterceptor

            app = Aura(middleware=[Middleware(RequestLogInterceptor)])

        To use this interceptor in a custom chain, pass it to ``Aura``::

            app = Aura(interceptors=[ChainRequestLogInterceptor()])
    """

    def __init__(self, log_headers: bool = False, log_body: bool = False) -> None:
        self.log_headers = log_headers
        self.log_body = log_body
        self._sanitizer = Sanitizer(list(DEFAULT_SENSITIVE_FIELDS))

    async def intercept(
        self,
        request: Any,
        handler: Callable[..., Awaitable[Any]],
        call_next: Callable[..., Awaitable[Any]],
    ) -> Any:
        """Log the request before processing and the response after.

        Args:
            request: The incoming request.
            handler: Original handler (not used directly; call_next wraps it).
            call_next: Callable to proceed to the next interceptor/handler.

        Returns:
            The response from the next layer.
        """
        start = time.perf_counter()

        method = getattr(request, "method", "?")
        path = getattr(getattr(request, "url", None), "path", str(request))

        if self.log_headers:
            headers = dict(getattr(request, "headers", {}))
            sanitized = self._sanitizer.sanitize_headers(headers)
            logger.debug("Request headers: %s", sanitized)

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start) * 1000
        status = getattr(response, "status_code", "?")

        # Get context variables (request_id, user_id, etc.)
        context = get_current_context()

        # Log with structured fields for JSON parsing
        logger.info(
            "%s %s %s %.1fms",
            method,
            path,
            status,
            elapsed_ms,
            extra={
                "method": method,
                "path": path,
                "status_code": status,
                "elapsed_ms": round(elapsed_ms, 1),
                **context,
            },
        )

        return response


# Backward compatibility aliases
RequestLogInterceptor = ChainRequestLogInterceptor
LoggingInterceptor = ChainRequestLogInterceptor

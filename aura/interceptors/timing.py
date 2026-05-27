"""Timing interceptor — injects X-Process-Time header into every response."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aura.interceptors.base import Interceptor


class TimingInterceptor(Interceptor):
    """Adds an ``X-Process-Time`` header (in seconds) to every response.

    The header value is formatted as a float with 6 decimal places,
    e.g. ``X-Process-Time: 0.001234``.

    Example::

        app = Aura(interceptors=[TimingInterceptor()])

    The header will appear in all responses::

        HTTP/1.1 200 OK
        X-Process-Time: 0.003142
    """

    HEADER_NAME = "X-Process-Time"

    async def intercept(
        self,
        request: Any,
        handler: Callable[..., Awaitable[Any]],
        call_next: Callable[..., Awaitable[Any]],
    ) -> Any:
        """Record start time, call next, then set header with elapsed time.

        Args:
            request: The incoming request.
            handler: The original handler (not called directly).
            call_next: Callable that invokes the next layer.

        Returns:
            The response with an additional ``X-Process-Time`` header.
        """
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        # Attempt to set header — works for Starlette Response objects.
        try:
            response.headers[self.HEADER_NAME] = f"{elapsed:.6f}"
        except (AttributeError, TypeError):
            # Response object doesn't support headers — silently skip.
            pass

        return response

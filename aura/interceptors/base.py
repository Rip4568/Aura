"""Abstract base class for Aura interceptors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any


class Interceptor(ABC):
    """Abstract base for request/response interceptors.

    Interceptors wrap request handlers, allowing arbitrary code to run
    *before* and *after* each request is processed.  They are useful for:

    * Structured logging
    * Request timing / performance metrics
    * Response transformation
    * Caching
    * Audit trails

    Interceptors are applied in registration order.  Each interceptor
    receives the request, the original handler, and a ``call_next``
    callable that invokes the next layer.

    Example::

        class TimingInterceptor(Interceptor):
            async def intercept(self, request, handler, call_next):
                start = time.perf_counter()
                response = await call_next(request)
                elapsed = time.perf_counter() - start
                response.headers["X-Process-Time"] = f"{elapsed:.4f}"
                return response
    """

    @abstractmethod
    async def intercept(
        self,
        request: Any,
        handler: Callable[..., Awaitable[Any]],
        call_next: Callable[..., Awaitable[Any]],
    ) -> Any:
        """Process the request, optionally modifying request/response.

        Args:
            request: The incoming request object.
            handler: The original route handler coroutine.
            call_next: Callable that invokes the next interceptor (or the
                       actual handler at the end of the chain).

        Returns:
            The response to send to the client.
        """
        ...

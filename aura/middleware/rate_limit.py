"""Rate-limiting ASGI middleware for Aura."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from aura.middleware.rate_limit_backends.base import RateLimitBackend
from aura.middleware.rate_limit_backends.memory import MemoryBackend

# ASGI type aliases
Scope = dict[str, Any]
Receive = Callable[[], Any]
Send = Callable[[dict[str, Any]], Any]


class RateLimitMiddleware:
    """Simple sliding-window rate limiter middleware.

    Limits the number of requests per time window per IP address (or a
    custom key extractor).  When the limit is exceeded the middleware
    returns an HTTP 429 response without invoking the inner application.

    Args:
        max_requests: Maximum number of allowed requests in the window.
        window_seconds: Length of the sliding window in seconds.
        key_func: Callable that returns the rate-limit key for a request.
                  Defaults to the client IP address extracted from the
                  ASGI scope.
        backend: Storage backend for request counters.  Defaults to
                 :class:`~aura.middleware.rate_limit_backends.memory.MemoryBackend`.
        status_code: HTTP status code returned when limit is exceeded
                     (default 429).
        message: Response body message.

    Example::

        app = Aura(
            middleware=[
                RateLimitMiddleware(max_requests=100, window_seconds=60),
            ]
        )
    """

    def __init__(
        self,
        app: Any,
        *,
        max_requests: int = 100,
        window_seconds: int = 60,
        key_func: Callable[[Scope], str] | None = None,
        backend: RateLimitBackend | None = None,
        status_code: int = 429,
        message: str = "Too Many Requests",
    ) -> None:
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key
        self._backend = backend or MemoryBackend()
        self.status_code = status_code
        self.message = message

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        """ASGI callable — check rate limit then delegate or reject."""
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        key = self.key_func(scope)
        allowed, remaining = await self._backend.acquire(
            key,
            max_requests=self.max_requests,
            window_seconds=float(self.window_seconds),
        )

        if not allowed:
            retry_after = max(1, int(self.window_seconds))
            await self._send_429(send, retry_after=retry_after)
            return

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-ratelimit-limit", str(self.max_requests).encode()),
                        (b"x-ratelimit-remaining", str(remaining).encode()),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _send_429(self, send: Any, *, retry_after: int) -> None:
        """Send an HTTP 429 Too Many Requests response."""
        body = self.message.encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [
                    (b"content-type", b"text/plain"),
                    (b"content-length", str(len(body)).encode()),
                    (b"retry-after", str(retry_after).encode()),
                    (b"x-ratelimit-limit", str(self.max_requests).encode()),
                    (b"x-ratelimit-remaining", b"0"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})

    @staticmethod
    def _default_key(scope: Scope) -> str:
        """Extract the client IP address as the rate-limit key."""
        client = scope.get("client")
        if client:
            return cast(str, client[0])
        # Fallback: try X-Forwarded-For from headers
        headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
        for name, value in headers:
            if name.lower() == b"x-forwarded-for":
                return value.decode().split(",")[0].strip()
        return "unknown"

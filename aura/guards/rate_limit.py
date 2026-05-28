"""RateLimitGuard — per-route rate limiting guard."""
from __future__ import annotations

import time
from collections import defaultdict
from collections.abc import Callable

from starlette.requests import Request

from aura.guards.base import Guard
from aura.exceptions.http import HTTPException


class RateLimitGuard(Guard):
    """Per-route sliding-window rate limiter.

    Unlike :class:`~aura.middleware.rate_limit.RateLimitMiddleware` (which applies
    globally at ASGI level), this Guard can be applied to specific routes or modules.

    Usage::

        limit = RateLimitGuard(max_requests=5, window_seconds=60)

        @post("/login", guards=[limit])
        async def login(self, body: Annotated[LoginDTO, Body()]) -> ...:
            ...

    Args:
        max_requests: Allowed requests in the time window.
        window_seconds: Length of the sliding window in seconds.
        key_func: Callable to extract the rate-limit key from a request.
                  Defaults to client IP.
        message: Error message when limit is exceeded.
    """

    def __init__(
        self,
        *,
        max_requests: int = 60,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] | None = None,
        message: str = "Rate limit exceeded. Please try again later.",
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key
        self.message = message
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def can_activate(self, request: Request) -> bool:
        key = self.key_func(request)
        now = time.monotonic()
        window_start = now - self.window_seconds
        history = self._requests[key]
        self._requests[key] = [ts for ts in history if ts >= window_start]
        if len(self._requests[key]) >= self.max_requests:
            return False
        self._requests[key].append(now)
        return True

    async def on_denied(self, request: Request) -> None:
        raise HTTPException(status_code=429, message=self.message)

    @staticmethod
    def _default_key(request: Request) -> str:
        client = request.client
        if client:
            return client.host
        forwarded = request.headers.get("x-forwarded-for", "")
        return forwarded.split(",")[0].strip() if forwarded else "unknown"

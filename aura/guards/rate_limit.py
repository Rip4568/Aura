"""RateLimitGuard — per-route rate limiting guard."""
from __future__ import annotations

import time
from collections.abc import Callable

from starlette.requests import Request

from aura.exceptions.http import HTTPException
from aura.guards.base import Guard


class RateLimitGuard(Guard):
    """Per-route sliding-window rate limiter with LRU memory management.

    Unlike :class:`~aura.middleware.rate_limit.RateLimitMiddleware` (which applies
    globally at ASGI level), this Guard can be applied to specific routes or modules.

    Memory is bounded via LRU eviction: when more keys are tracked than
    ``max_tracked_keys``, the oldest key is removed.

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
        max_tracked_keys: Maximum number of unique keys to track in memory.
                         When exceeded, the oldest key is evicted (LRU).
    """

    def __init__(
        self,
        *,
        max_requests: int = 60,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] | None = None,
        message: str = "Rate limit exceeded. Please try again later.",
        max_tracked_keys: int = 10000,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key
        self.message = message
        self.max_tracked_keys = max_tracked_keys
        self._requests: dict[str, list[float]] = {}
        self._key_order: list[str] = []

    async def can_activate(self, request: Request) -> bool:
        key = self.key_func(request)
        now = time.monotonic()
        window_start = now - self.window_seconds

        # Clean up old memory if we're over the limit
        if len(self._requests) > self.max_tracked_keys:
            self._cleanup_oldest_key()

        # Get or create history for this key
        history = self._requests.get(key, [])
        # Filter out timestamps outside the window
        self._requests[key] = [ts for ts in history if ts >= window_start]

        # Check if limit exceeded
        if len(self._requests[key]) >= self.max_requests:
            return False

        # Add current request timestamp
        self._requests[key].append(now)

        # Track key order for LRU (move to end if already exists, or add if new)
        if key in self._key_order:
            self._key_order.remove(key)
        self._key_order.append(key)

        return True

    async def on_denied(self, request: Request) -> None:
        """Raise HTTPException with rate limit headers."""
        raise HTTPException(
            status_code=429,
            message=self.message,
            headers={
                "X-RateLimit-Limit": str(self.max_requests),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(self.window_seconds),
            },
        )

    def _cleanup_oldest_key(self) -> None:
        """Remove the oldest tracked key to stay under max_tracked_keys."""
        if self._key_order:
            oldest = self._key_order.pop(0)
            self._requests.pop(oldest, None)

    @staticmethod
    def _default_key(request: Request) -> str:
        client = request.client
        if client:
            return client.host
        forwarded = request.headers.get("x-forwarded-for", "")
        return forwarded.split(",")[0].strip() if forwarded else "unknown"

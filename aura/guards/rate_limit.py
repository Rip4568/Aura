"""RateLimitGuard — per-route rate limiting guard."""
from __future__ import annotations

from collections.abc import Callable

from starlette.requests import Request

from aura.exceptions.http import HTTPException
from aura.guards.base import Guard
from aura.middleware.client_ip import resolve_client_ip
from aura.middleware.rate_limit_backends.base import RateLimitBackend
from aura.middleware.rate_limit_backends.memory import MemoryBackend


class RateLimitGuard(Guard):
    """Per-route sliding-window rate limiter with LRU memory management.

    Unlike :class:`~aura.middleware.rate_limit.RateLimitMiddleware` (which applies
    globally at ASGI level), this Guard can be applied to specific routes or modules.

    Memory is bounded via LRU eviction: when more keys are tracked than
    ``max_tracked_keys``, the oldest key is removed (in-memory backend only).

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
        trusted_proxies: IP addresses of reverse proxies allowed to set
                         ``X-Forwarded-For``.
        backend: Storage backend for request counters.  Defaults to
                 :class:`~aura.middleware.rate_limit_backends.memory.MemoryBackend`
                 with LRU eviction.
        message: Error message when limit is exceeded.
        max_tracked_keys: Maximum number of unique keys to track in memory
                         when using the default backend.
    """

    def __init__(
        self,
        *,
        max_requests: int = 60,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] | None = None,
        trusted_proxies: list[str] | None = None,
        backend: RateLimitBackend | None = None,
        message: str = "Rate limit exceeded. Please try again later.",
        max_tracked_keys: int = 10000,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._make_default_key(trusted_proxies)
        self._trusted_proxies = (
            frozenset(trusted_proxies) if trusted_proxies else None
        )
        self.message = message
        self.max_tracked_keys = max_tracked_keys
        self._backend = backend or MemoryBackend(max_tracked_keys=max_tracked_keys)

    async def can_activate(self, request: Request) -> bool:
        key = self.key_func(request)
        allowed, _ = await self._backend.acquire(
            key,
            max_requests=self.max_requests,
            window_seconds=float(self.window_seconds),
        )
        return allowed

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

    @staticmethod
    def _make_default_key(
        trusted_proxies: list[str] | None,
    ) -> Callable[[Request], str]:
        proxies = frozenset(trusted_proxies) if trusted_proxies else None

        def _default_key(request: Request) -> str:
            client_host = request.client.host if request.client else None
            forwarded = request.headers.get("x-forwarded-for")
            return resolve_client_ip(client_host, forwarded, proxies)

        return _default_key

    @staticmethod
    def _default_key(request: Request) -> str:
        client = request.client
        if client:
            return client.host
        forwarded = request.headers.get("x-forwarded-for", "")
        return forwarded.split(",")[0].strip() if forwarded else "unknown"

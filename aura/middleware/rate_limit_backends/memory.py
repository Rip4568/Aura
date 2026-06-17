"""In-memory sliding-window rate-limit backend."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict

from aura.middleware.rate_limit_backends.base import RateLimitBackend


class MemoryBackend(RateLimitBackend):
    """Process-local sliding-window rate limiter backed by a dict.

    Args:
        max_tracked_keys: When set, evict the oldest key once this many
            unique keys are tracked (LRU).  Omit for unbounded key storage
            (suitable for ASGI middleware).
    """

    def __init__(self, *, max_tracked_keys: int | None = None) -> None:
        self._max_tracked_keys = max_tracked_keys
        self._use_defaultdict = max_tracked_keys is None
        if self._use_defaultdict:
            self._requests: dict[str, list[float]] = defaultdict(list)
        else:
            self._requests = {}
        self._key_order: list[str] = []
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: float,
    ) -> tuple[bool, int]:
        now = time.monotonic()
        window_start = now - window_seconds

        async with self._lock:
            if self._max_tracked_keys is not None and len(self._requests) > self._max_tracked_keys:
                self._cleanup_oldest_key()

            if self._use_defaultdict:
                history = self._requests[key]
            else:
                history = self._requests.get(key, [])

            pruned = [ts for ts in history if ts >= window_start]

            if len(pruned) >= max_requests:
                return False, 0

            pruned.append(now)
            self._requests[key] = pruned

            if self._max_tracked_keys is not None:
                if key in self._key_order:
                    self._key_order.remove(key)
                self._key_order.append(key)

            remaining = max(0, max_requests - len(pruned))
            return True, remaining

    def _cleanup_oldest_key(self) -> None:
        if self._key_order:
            oldest = self._key_order.pop(0)
            self._requests.pop(oldest, None)

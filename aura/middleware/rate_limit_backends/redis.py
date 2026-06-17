"""Redis-backed sliding-window rate-limit backend."""

from __future__ import annotations

import time
from typing import Any

from aura.middleware.rate_limit_backends.base import RateLimitBackend


class RedisBackend(RateLimitBackend):
    """Distributed sliding-window rate limiter backed by Redis sorted sets.

    Requires the ``redis`` extra:

    .. code-block:: shell

        pip install aura-web[redis]

    Args:
        redis_url: Redis connection URL.
        key_prefix: Prefix applied to every rate-limit key in Redis.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        *,
        key_prefix: str = "aura:ratelimit:",
    ) -> None:
        self._redis_url = redis_url
        self._key_prefix = key_prefix
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        if self._redis is None:
            try:
                from redis.asyncio import Redis
            except ImportError as exc:
                raise RuntimeError(
                    "RedisBackend requires the 'redis' package. "
                    "Install with: pip install aura-web[redis]"
                ) from exc
            self._redis = Redis.from_url(self._redis_url)
        return self._redis

    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: float,
    ) -> tuple[bool, int]:
        redis = await self._get_redis()
        full_key = f"{self._key_prefix}{key}"
        now = time.time()
        window_start = now - window_seconds

        pipe = redis.pipeline()
        pipe.zremrangebyscore(full_key, 0, window_start)
        pipe.zcard(full_key)
        _, current_count = await pipe.execute()

        if current_count >= max_requests:
            return False, 0

        member = f"{now:.6f}"
        await redis.zadd(full_key, {member: now})
        await redis.expire(full_key, int(window_seconds) + 1)

        remaining = max(0, max_requests - current_count - 1)
        return True, remaining

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

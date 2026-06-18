"""Redis-backed sliding-window rate-limit backend."""

from __future__ import annotations

import time
import uuid
from typing import Any

from aura.middleware.rate_limit_backends.base import RateLimitBackend

_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local window_start = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local window_seconds = tonumber(ARGV[4])
local member = ARGV[5]

redis.call('ZREMRANGEBYSCORE', key, 0, window_start)
local current_count = redis.call('ZCARD', key)
if current_count >= max_requests then
    return {0, 0}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window_seconds + 1)
local remaining = max_requests - current_count - 1
return {1, remaining}
"""


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
        self._script: Any = None

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
            self._script = self._redis.register_script(_ACQUIRE_SCRIPT)
        return self._redis

    async def acquire(
        self,
        key: str,
        *,
        max_requests: int,
        window_seconds: float,
    ) -> tuple[bool, int]:
        await self._get_redis()
        full_key = f"{self._key_prefix}{key}"
        now = time.time()
        window_start = now - window_seconds
        member = f"{now:.6f}:{uuid.uuid4().hex}"

        allowed, remaining = await self._script(
            keys=[full_key],
            args=[
                window_start,
                now,
                max_requests,
                int(window_seconds) + 1,
                member,
            ],
        )

        if int(allowed) == 0:
            return False, 0
        return True, int(remaining)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            self._script = None

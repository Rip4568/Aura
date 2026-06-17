"""Rate-limit storage backends for Aura middleware and guards."""

from __future__ import annotations

from typing import Any

from aura.middleware.rate_limit_backends.base import RateLimitBackend
from aura.middleware.rate_limit_backends.memory import MemoryBackend

__all__ = ["MemoryBackend", "RateLimitBackend", "RedisBackend"]


def __getattr__(name: str) -> Any:
    if name == "RedisBackend":
        from aura.middleware.rate_limit_backends.redis import RedisBackend

        return RedisBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

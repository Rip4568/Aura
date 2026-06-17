"""Tests for Redis rate-limit backend (optional — requires redis extra)."""

from __future__ import annotations

import importlib.util

import pytest

from aura.middleware.rate_limit_backends.memory import MemoryBackend

redis_installed = importlib.util.find_spec("redis") is not None


@pytest.mark.skipif(not redis_installed, reason="redis package not installed")
class TestRedisBackend:
    @pytest.mark.asyncio
    async def test_redis_backend_lazy_import(self) -> None:
        from aura.middleware.rate_limit_backends import RedisBackend

        assert RedisBackend is not None

    @pytest.mark.asyncio
    async def test_redis_backend_acquire_without_server(self) -> None:
        """RedisBackend raises on connection failure when Redis is unreachable."""
        from aura.middleware.rate_limit_backends.redis import RedisBackend

        backend = RedisBackend(redis_url="redis://127.0.0.1:16379")
        with pytest.raises(Exception):
            await backend.acquire("test-key", max_requests=5, window_seconds=60)
        await backend.close()


class TestMemoryBackend:
    @pytest.mark.asyncio
    async def test_memory_backend_acquire(self) -> None:
        backend = MemoryBackend()
        allowed, remaining = await backend.acquire(
            "client-1", max_requests=2, window_seconds=60
        )
        assert allowed is True
        assert remaining == 1

        allowed, remaining = await backend.acquire(
            "client-1", max_requests=2, window_seconds=60
        )
        assert allowed is True
        assert remaining == 0

        allowed, remaining = await backend.acquire(
            "client-1", max_requests=2, window_seconds=60
        )
        assert allowed is False
        assert remaining == 0

"""Tests for Redis rate-limit backend (optional — requires redis extra)."""

from __future__ import annotations

import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

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

    @pytest.mark.asyncio
    async def test_redis_backend_acquire_uses_atomic_script(self) -> None:
        """acquire() must use a single Lua script (no TOCTOU race)."""
        from aura.middleware.rate_limit_backends.redis import RedisBackend

        mock_script = AsyncMock(return_value=[1, 4])
        mock_redis = MagicMock()
        mock_redis.register_script = MagicMock(return_value=mock_script)

        with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
            backend = RedisBackend()
            allowed, remaining = await backend.acquire(
                "client-1", max_requests=5, window_seconds=60
            )

        assert allowed is True
        assert remaining == 4
        mock_script.assert_awaited_once()
        mock_redis.register_script.assert_called_once()


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

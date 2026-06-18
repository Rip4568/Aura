"""Event bus backend implementations."""

from __future__ import annotations

from aura.events.backends.memory import InMemoryEventBus

__all__ = ["InMemoryEventBus"]

try:
    from aura.events.backends.redis_streams import RedisStreamsEventBus
except ImportError:
    RedisStreamsEventBus = None  # type: ignore[misc, assignment]

if RedisStreamsEventBus is not None:
    __all__.append("RedisStreamsEventBus")

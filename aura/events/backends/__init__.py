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

try:
    from aura.events.backends.rabbitmq import RabbitMQEventBus
except ImportError:
    RabbitMQEventBus = None  # type: ignore[misc, assignment]

if RabbitMQEventBus is not None:
    __all__.append("RabbitMQEventBus")

try:
    from aura.events.backends.kafka import KafkaEventBus
except ImportError:
    KafkaEventBus = None  # type: ignore[misc, assignment]

if KafkaEventBus is not None:
    __all__.append("KafkaEventBus")

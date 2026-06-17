"""Aura event bus — pub/sub with pluggable backends."""

from aura.events.backends.memory import InMemoryEventBus
from aura.events.base import EventBus, EventEnvelope
from aura.events.decorators import get_event_bus, on_event, set_event_bus
from aura.events.module import AuraEventsModule
from aura.events.registry import EventHandlerDefinition, EventHandlerRegistry

__all__ = [
    "AuraEventsModule",
    "EventBus",
    "EventEnvelope",
    "EventHandlerDefinition",
    "EventHandlerRegistry",
    "InMemoryEventBus",
    "get_event_bus",
    "on_event",
    "set_event_bus",
]

try:
    from aura.events.backends.redis_streams import RedisStreamsEventBus
except ImportError:
    RedisStreamsEventBus = None  # type: ignore[misc, assignment]
else:
    __all__.append("RedisStreamsEventBus")

"""Registry for event handlers registered via decorators."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class EventHandlerDefinition:
    """Metadata for a handler registered with :func:`~aura.events.decorators.on_event`."""

    func: Callable[..., Any]
    topic: str
    name: str


class EventHandlerRegistry:
    """Global registry mapping topics to event handler definitions."""

    _handlers: dict[str, list[EventHandlerDefinition]] = {}

    @classmethod
    def register(cls, definition: EventHandlerDefinition) -> None:
        """Register a handler for its topic.

        Args:
            definition: Handler metadata from the decorator.
        """
        cls._handlers.setdefault(definition.topic, []).append(definition)

    @classmethod
    def get(cls, topic: str) -> list[EventHandlerDefinition]:
        """Return all handlers registered for *topic*."""
        return list(cls._handlers.get(topic, []))

    @classmethod
    def all(cls) -> dict[str, list[EventHandlerDefinition]]:
        """Return a copy of all registered handlers grouped by topic."""
        return {topic: list(handlers) for topic, handlers in cls._handlers.items()}

    @classmethod
    def clear(cls) -> None:
        """Remove all registered handlers (used in tests)."""
        cls._handlers.clear()

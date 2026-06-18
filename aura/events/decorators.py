"""Decorators for registering Aura event handlers."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, TypeVar

from aura.events.base import EventBus
from aura.events.registry import EventHandlerDefinition, EventHandlerRegistry

F = TypeVar("F", bound=Callable[..., Any])

_default_bus: EventBus | None = None


def on_event(topic: str, *, name: str | None = None) -> Callable[[F], F]:
    """Register an async function as an event handler for *topic*.

    Args:
        topic: Event channel to subscribe to.
        name: Override the default qualified-name handler identifier.

    Returns:
        A decorator that registers the function and attaches metadata.

    Example::

        @on_event("user.created")
        async def on_user_created(event: EventEnvelope) -> None:
            await email_service.send_welcome(event.payload["email"])
    """

    def decorator(func: F) -> F:
        handler_name = name or f"{func.__module__}.{func.__qualname__}"
        # Instance methods are discovered via __aura_event__ during module
        # wiring; only register standalone callables in the global registry.
        params = list(inspect.signature(func).parameters)
        is_instance_method = bool(params) and params[0] == "self"
        if not is_instance_method:
            definition = EventHandlerDefinition(
                func=func,
                topic=topic,
                name=handler_name,
            )
            EventHandlerRegistry.register(definition)
        func.__aura_event__ = {  # type: ignore[attr-defined]
            "topic": topic,
            "name": handler_name,
        }
        return func

    return decorator


def set_event_bus(bus: EventBus | None) -> None:
    """Replace the global default event bus.

    Called by :class:`~aura.core.app.Aura` during startup when a bus is
    configured.

    Args:
        bus: An :class:`~aura.events.base.EventBus` instance.
    """
    global _default_bus
    _default_bus = bus


def get_event_bus() -> EventBus | None:
    """Return the global default event bus, if initialised."""
    return _default_bus

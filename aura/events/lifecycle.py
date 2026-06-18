"""Event bus lifecycle helpers."""

from __future__ import annotations

import logging
from typing import Any, cast

from aura.events.base import EventBus
from aura.events.decorators import set_event_bus
from aura.events.wiring import create_event_bus_from_config, wire_event_handlers

logger = logging.getLogger("aura.events")

_events_started = False


async def ensure_events_started(
    *,
    container: Any,
    registry: Any,
    bus: EventBus | None = None,
    events_config: Any | None = None,
) -> EventBus | None:
    """Initialise the event bus once per application lifecycle.

    Args:
        container: Application DI container.
        registry: Application module registry.
        bus: Explicit bus instance (takes precedence over config).
        events_config: ``EventsConfig`` used when *bus* is ``None``.

    Returns:
        The started :class:`~aura.events.base.EventBus`, or ``None`` if
        events are disabled.
    """
    global _events_started

    from aura.events.base import EventBus as EventBusType

    if container.is_registered(EventBusType):
        existing = await container.resolve(EventBusType)
        return cast(EventBus, existing)

    if _events_started:
        return None

    bus_instance = bus
    if bus_instance is None and events_config is not None and events_config.enabled:
        bus_instance = create_event_bus_from_config(events_config)

    if bus_instance is None:
        return None

    await wire_event_handlers(bus_instance, registry, container)
    await bus_instance.startup()
    container.register_instance(EventBusType, bus_instance)
    set_event_bus(bus_instance)
    _events_started = True
    logger.info("Event bus started (%s)", type(bus_instance).__name__)
    return bus_instance


def reset_events_lifecycle() -> None:
    """Reset the module-level started flag (used in tests)."""
    global _events_started
    _events_started = False

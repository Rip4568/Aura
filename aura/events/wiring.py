"""Wire event handlers from registry and module metadata onto an EventBus."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aura.events.base import EventBus, EventEnvelope, EventHandler
from aura.events.microservice import MessageHandlerRegistry
from aura.events.registry import EventHandlerRegistry

logger = logging.getLogger("aura.events")


def _make_bound_handler(
    func: Callable[..., Any],
    *,
    instance: Any | None = None,
) -> EventHandler:
    """Wrap a function or bound method as an :class:`EventHandler`."""

    async def _handler(envelope: EventEnvelope) -> None:
        if instance is not None:
            bound = getattr(instance, func.__name__)
            await bound(envelope)
        else:
            await func(envelope)

    return _handler


def _make_event_pattern_handler(
    func: Callable[..., Any],
    *,
    instance: Any | None = None,
) -> EventHandler:
    """Wrap an ``@EventPattern`` handler (receives payload, not envelope)."""

    async def _handler(envelope: EventEnvelope) -> None:
        if instance is not None:
            bound = getattr(instance, func.__name__)
            await bound(envelope.payload)
        else:
            await func(envelope.payload)

    return _handler


def _make_message_pattern_handler(
    func: Callable[..., Any],
    *,
    instance: Any | None = None,
) -> Callable[[Any], Awaitable[Any]]:
    """Wrap an ``@MessagePattern`` handler for request/response."""

    async def _handler(payload: Any) -> Any:
        if instance is not None:
            bound = getattr(instance, func.__name__)
            return await bound(payload)
        return await func(payload)

    return _handler


def _iter_class_event_methods(cls: type) -> list[tuple[str, Callable[..., Any]]]:
    """Return ``(topic, method)`` pairs for methods decorated with ``@on_event``."""
    found: list[tuple[str, Callable[..., Any]]] = []
    for _name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
        meta = getattr(member, "__aura_event__", None)
        if meta and "topic" in meta:
            found.append((meta["topic"], member))
    for _name, member in inspect.getmembers(cls):
        if not callable(member):
            continue
        meta = getattr(member, "__aura_event__", None)
        if meta and "topic" in meta and not any(m is member for _, m in found):
            found.append((meta["topic"], member))
    return found


def _iter_class_message_methods(
    cls: type,
) -> list[tuple[str, str, Callable[..., Any]]]:
    """Return ``(topic, pattern, method)`` for ``@EventPattern`` / ``@MessagePattern``."""
    found: list[tuple[str, str, Callable[..., Any]]] = []
    for _name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
        meta = getattr(member, "__aura_message__", None)
        if meta and "topic" in meta and "pattern" in meta:
            found.append((meta["topic"], meta["pattern"], member))
    for _name, member in inspect.getmembers(cls):
        if not callable(member):
            continue
        meta = getattr(member, "__aura_message__", None)
        if (
            meta
            and "topic" in meta
            and "pattern" in meta
            and not any(m is member for _, _, m in found)
        ):
            found.append((meta["topic"], meta["pattern"], member))
    return found


async def _wire_message_pattern(
    bus: EventBus,
    topic: str,
    handler: Callable[[Any], Awaitable[Any]],
    *,
    key: str,
    wired: set[tuple[str, str]],
) -> None:
    """Register a request/response handler when the backend supports it."""
    register = getattr(bus, "register_message_handler", None)
    if register is None:
        logger.warning(
            "Backend %s does not support @MessagePattern for %s",
            type(bus).__name__,
            key,
        )
        return
    await register(topic, handler)
    wired.add((topic, key))
    logger.debug("Wired message handler %s -> %r", key, topic)


async def wire_event_handlers(
    bus: EventBus,
    registry: Any,
    container: Any,
) -> None:
    """Subscribe all registered handlers and module methods to *bus*.

    Sources:
    1. :class:`~aura.events.registry.EventHandlerRegistry` (``@on_event``).
    2. :class:`~aura.events.microservice.MessageHandlerRegistry`
       (``@EventPattern`` / ``@MessagePattern``).
    3. Controller and provider methods with ``__aura_event__`` or ``__aura_message__``.

    Args:
        bus: The event bus to wire handlers onto.
        registry: Application :class:`~aura.modules.registry.ModuleRegistry`.
        container: Application DI container for resolving controller instances.
    """
    wired: set[tuple[str, str]] = set()

    for topic, definitions in EventHandlerRegistry.all().items():
        for definition in definitions:
            key = (topic, definition.name)
            if key in wired:
                continue
            await bus.subscribe(topic, _make_bound_handler(definition.func))
            wired.add(key)
            logger.debug("Wired event handler %s -> %r", definition.name, topic)

    for topic, message_definitions in MessageHandlerRegistry.all().items():
        for message_def in message_definitions:
            key = (topic, message_def.name)
            if key in wired:
                continue
            if message_def.pattern == "event":
                await bus.subscribe(
                    topic,
                    _make_event_pattern_handler(message_def.func),
                )
                wired.add(key)
                logger.debug(
                    "Wired event pattern handler %s -> %r", message_def.name, topic
                )
            elif message_def.pattern == "message":
                await _wire_message_pattern(
                    bus,
                    topic,
                    _make_message_pattern_handler(message_def.func),
                    key=message_def.name,
                    wired=wired,
                )

    for module_class in getattr(registry, "_modules", []):
        meta = module_class.__aura_module__
        for controller_cls in meta.controllers:
            for topic, method in _iter_class_event_methods(controller_cls):
                key = (topic, f"{controller_cls.__name__}.{method.__name__}")
                if key in wired:
                    continue
                try:
                    instance = await container.resolve(controller_cls)
                except Exception:
                    logger.exception(
                        "Could not resolve controller %s for event wiring",
                        controller_cls.__name__,
                    )
                    continue
                bound = getattr(instance, method.__name__)
                await bus.subscribe(topic, _make_bound_handler(bound, instance=instance))
                wired.add(key)
                logger.debug(
                    "Wired controller handler %s.%s -> %r",
                    controller_cls.__name__,
                    method.__name__,
                    topic,
                )

            for topic, pattern, method in _iter_class_message_methods(controller_cls):
                key = (topic, f"{controller_cls.__name__}.{method.__name__}")
                if key in wired:
                    continue
                try:
                    instance = await container.resolve(controller_cls)
                except Exception:
                    logger.exception(
                        "Could not resolve controller %s for message wiring",
                        controller_cls.__name__,
                    )
                    continue
                bound = getattr(instance, method.__name__)
                if pattern == "event":
                    await bus.subscribe(
                        topic,
                        _make_event_pattern_handler(bound, instance=instance),
                    )
                    wired.add(key)
                    logger.debug(
                        "Wired controller event pattern %s.%s -> %r",
                        controller_cls.__name__,
                        method.__name__,
                        topic,
                    )
                elif pattern == "message":
                    await _wire_message_pattern(
                        bus,
                        topic,
                        _make_message_pattern_handler(bound, instance=instance),
                        key=key[1],
                        wired=wired,
                    )

        for provider_cls in meta.providers:
            for topic, method in _iter_class_event_methods(provider_cls):
                key = (topic, f"{provider_cls.__name__}.{method.__name__}")
                if key in wired:
                    continue
                try:
                    instance = await container.resolve(provider_cls)
                except Exception:
                    logger.exception(
                        "Could not resolve provider %s for event wiring",
                        provider_cls.__name__,
                    )
                    continue
                bound = getattr(instance, method.__name__)
                await bus.subscribe(topic, _make_bound_handler(bound, instance=instance))
                wired.add(key)
                logger.debug(
                    "Wired provider handler %s.%s -> %r",
                    provider_cls.__name__,
                    method.__name__,
                    topic,
                )

            for topic, pattern, method in _iter_class_message_methods(provider_cls):
                key = (topic, f"{provider_cls.__name__}.{method.__name__}")
                if key in wired:
                    continue
                try:
                    instance = await container.resolve(provider_cls)
                except Exception:
                    logger.exception(
                        "Could not resolve provider %s for message wiring",
                        provider_cls.__name__,
                    )
                    continue
                bound = getattr(instance, method.__name__)
                if pattern == "event":
                    await bus.subscribe(
                        topic,
                        _make_event_pattern_handler(bound, instance=instance),
                    )
                    wired.add(key)
                    logger.debug(
                        "Wired provider event pattern %s.%s -> %r",
                        provider_cls.__name__,
                        method.__name__,
                        topic,
                    )
                elif pattern == "message":
                    await _wire_message_pattern(
                        bus,
                        topic,
                        _make_message_pattern_handler(bound, instance=instance),
                        key=key[1],
                        wired=wired,
                    )


def create_event_bus_from_config(events_config: Any) -> EventBus:
    """Instantiate an :class:`~aura.events.base.EventBus` from config.

    Args:
        events_config: :class:`~aura.config.base.EventsConfig` instance.

    Returns:
        A concrete event bus backend.

    Raises:
        ValueError: If *backend* is not recognised.
    """
    backend = events_config.backend.lower()
    if backend == "memory":
        from aura.events.backends.memory import InMemoryEventBus

        return InMemoryEventBus()
    if backend == "redis_streams":
        from aura.events.backends.redis_streams import RedisStreamsEventBus

        return RedisStreamsEventBus(
            redis_url=events_config.redis_url,
            stream_prefix=events_config.stream_prefix,
        )
    if backend == "rabbitmq":
        from aura.events.backends.rabbitmq import RabbitMQEventBus

        return RabbitMQEventBus(rabbitmq_url=events_config.rabbitmq_url)
    if backend == "kafka":
        from aura.events.backends.kafka import KafkaEventBus

        return KafkaEventBus(
            bootstrap_servers=events_config.kafka_bootstrap_servers,
            consumer_group=events_config.kafka_consumer_group,
        )
    raise ValueError(
        f"Unknown events backend {events_config.backend!r}. "
        "Expected 'memory', 'redis_streams', 'rabbitmq', or 'kafka'."
    )

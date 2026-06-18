"""NestJS-style microservice decorators for event and message patterns."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

MessageHandlerFunc = Callable[..., Awaitable[Any]]


@dataclass
class MessageHandlerDefinition:
    """Metadata for a handler registered with pattern decorators."""

    func: MessageHandlerFunc
    topic: str
    pattern: str
    name: str


class MessageHandlerRegistry:
    """Global registry mapping topics to message/event pattern handlers."""

    _handlers: dict[str, list[MessageHandlerDefinition]] = {}

    @classmethod
    def register(cls, definition: MessageHandlerDefinition) -> None:
        """Register a handler for its topic."""
        cls._handlers.setdefault(definition.topic, []).append(definition)

    @classmethod
    def get(cls, topic: str) -> list[MessageHandlerDefinition]:
        """Return all handlers registered for *topic*."""
        return list(cls._handlers.get(topic, []))

    @classmethod
    def all(cls) -> dict[str, list[MessageHandlerDefinition]]:
        """Return a copy of all registered handlers grouped by topic."""
        return {topic: list(handlers) for topic, handlers in cls._handlers.items()}

    @classmethod
    def clear(cls) -> None:
        """Remove all registered handlers (used in tests)."""
        cls._handlers.clear()


def EventPattern(topic: str, *, name: str | None = None) -> Callable[[F], F]:  # noqa: N802
    """Register a fire-and-forget handler for *topic* (NestJS-style).

    Args:
        topic: Message routing key / channel name.
        name: Optional handler identifier override.

    Example::

        @EventPattern("user.created")
        async def on_user_created(data: dict) -> None:
            await notify(data["email"])
    """

    def decorator(func: F) -> F:
        handler_name = name or f"{func.__module__}.{func.__qualname__}"
        params = list(inspect.signature(func).parameters)
        is_instance_method = bool(params) and params[0] == "self"
        if not is_instance_method:
            MessageHandlerRegistry.register(
                MessageHandlerDefinition(
                    func=func,
                    topic=topic,
                    pattern="event",
                    name=handler_name,
                )
            )
        func.__aura_message__ = {  # type: ignore[attr-defined]
            "topic": topic,
            "pattern": "event",
            "name": handler_name,
        }
        return func

    return decorator


def MessagePattern(topic: str, *, name: str | None = None) -> Callable[[F], F]:  # noqa: N802
    """Register a request/response handler for *topic* (NestJS-style).

    Args:
        topic: Message routing key / channel name.
        name: Optional handler identifier override.

    Example::

        @MessagePattern("math.sum")
        async def sum_numbers(data: dict) -> dict:
            return {"result": data["a"] + data["b"]}
    """

    def decorator(func: F) -> F:
        handler_name = name or f"{func.__module__}.{func.__qualname__}"
        params = list(inspect.signature(func).parameters)
        is_instance_method = bool(params) and params[0] == "self"
        if not is_instance_method:
            MessageHandlerRegistry.register(
                MessageHandlerDefinition(
                    func=func,
                    topic=topic,
                    pattern="message",
                    name=handler_name,
                )
            )
        func.__aura_message__ = {  # type: ignore[attr-defined]
            "topic": topic,
            "pattern": "message",
            "name": handler_name,
        }
        return func

    return decorator

"""Base types and abstractions for the Aura event bus."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

EventHandler = Callable[["EventEnvelope"], Awaitable[None]]


@dataclass
class EventEnvelope:
    """Wrapper for a published event.

    Attributes:
        topic: Event channel name (e.g. ``"user.created"``).
        payload: Arbitrary serialisable event data.
        event_id: Unique identifier for this event instance.
        timestamp: UTC time when the event was created.
    """

    topic: str
    payload: Any
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


class EventBus(ABC):
    """Abstract pub/sub event bus.

    Concrete backends (memory, Redis Streams, …) implement publish/subscribe
    with optional startup/shutdown lifecycle hooks.
    """

    @abstractmethod
    async def publish(self, topic: str, payload: Any) -> EventEnvelope:
        """Publish an event to *topic*.

        Args:
            topic: Channel name.
            payload: Event data.

        Returns:
            The :class:`EventEnvelope` that was published.
        """
        ...

    @abstractmethod
    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Register *handler* to receive events on *topic*.

        Args:
            topic: Channel name.
            handler: Async callable receiving an :class:`EventEnvelope`.
        """
        ...

    @abstractmethod
    async def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        """Remove *handler* from *topic* subscriptions.

        Args:
            topic: Channel name.
            handler: Previously registered handler.
        """
        ...

    async def startup(self) -> None:
        """Initialise the backend (connections, consumer tasks, …)."""

    async def shutdown(self) -> None:
        """Gracefully stop the backend and release resources."""

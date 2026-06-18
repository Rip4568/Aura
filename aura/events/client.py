"""Client for emitting events and sending request/response messages."""

from __future__ import annotations

from typing import Any

from aura.events.base import EventBus, EventEnvelope


class MessagingClient:
    """High-level messaging client over an :class:`~aura.events.base.EventBus`.

    Args:
        bus: The active event bus backend.

    Example::

        client = MessagingClient(bus)
        await client.emit("user.created", {"id": 1})
        result = await client.send("math.sum", {"a": 1, "b": 2})
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def emit(self, topic: str, payload: Any) -> EventEnvelope:
        """Publish a fire-and-forget event to *topic*.

        Args:
            topic: Routing key / channel name.
            payload: Serializable event data.

        Returns:
            The published :class:`~aura.events.base.EventEnvelope`.
        """
        return await self._bus.publish(topic, payload)

    async def send(self, topic: str, payload: Any, *, timeout: float = 30.0) -> Any:
        """Send a request to *topic* and wait for a response.

        Requires a backend that supports request/response
        (``RabbitMQEventBus`` or ``KafkaEventBus``).

        Args:
            topic: Routing key / channel name.
            payload: Request data.
            timeout: Seconds to wait for a reply.

        Returns:
            The handler response payload.

        Raises:
            RuntimeError: If the backend does not support request/response.
            asyncio.TimeoutError: If no response arrives within *timeout*.
        """
        request = getattr(self._bus, "request", None)
        if request is None:
            raise RuntimeError(
                f"Request/response is not supported by {type(self._bus).__name__}. "
                "Use backend='rabbitmq' or backend='kafka'."
            )
        return await request(topic, payload, timeout=timeout)

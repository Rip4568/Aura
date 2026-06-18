"""In-memory event bus for development and testing."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from aura.events.base import EventBus, EventEnvelope, EventHandler

logger = logging.getLogger("aura.events")


class InMemoryEventBus(EventBus):
    """In-process event bus using asyncio queues per topic.

    Each topic has a dedicated queue consumed by a background task that
    fan-outs every :class:`~aura.events.base.EventEnvelope` to all
    registered subscribers.

    Example::

        bus = InMemoryEventBus()
        await bus.startup()

        received: list[EventEnvelope] = []

        async def handler(event: EventEnvelope) -> None:
            received.append(event)

        await bus.subscribe("user.created", handler)
        await bus.publish("user.created", {"id": 1})
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[EventEnvelope | None]] = {}
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._consumer_tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False

    async def publish(self, topic: str, payload: Any) -> EventEnvelope:
        envelope = EventEnvelope(topic=topic, payload=payload)
        queue = self._queues.setdefault(topic, asyncio.Queue())
        await queue.put(envelope)
        return envelope

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)
        if self._running:
            self._ensure_consumer(topic)

    async def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    async def startup(self) -> None:
        self._running = True
        for topic in list(self._subscribers.keys()):
            self._ensure_consumer(topic)

    async def shutdown(self) -> None:
        self._running = False
        for topic, task in list(self._consumer_tasks.items()):
            queue = self._queues.get(topic)
            if queue is not None:
                await queue.put(None)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consumer_tasks.clear()

    def _ensure_consumer(self, topic: str) -> None:
        if topic in self._consumer_tasks:
            return
        self._queues.setdefault(topic, asyncio.Queue())
        self._consumer_tasks[topic] = asyncio.create_task(self._consumer_loop(topic))

    async def _consumer_loop(self, topic: str) -> None:
        queue = self._queues[topic]
        while self._running:
            envelope = await queue.get()
            try:
                if envelope is None:
                    break
                for handler in list(self._subscribers.get(topic, [])):
                    try:
                        await handler(envelope)
                    except Exception:
                        logger.exception(
                            "Error in event handler for topic %r", topic
                        )
            finally:
                queue.task_done()

"""RabbitMQ event bus backend using aio-pika."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from aura.events.base import EventBus, EventEnvelope, EventHandler

logger = logging.getLogger("aura.events")

MessageHandler = Callable[[Any], Awaitable[Any]]


class RabbitMQEventBus(EventBus):
    """Distributed event bus backed by RabbitMQ topic exchange.

    Uses ``connect_robust`` for resilient connections and supports
    request/response via ``reply_to`` and ``correlation_id``.

    Requires the ``rabbitmq`` extra:

    .. code-block:: shell

        pip install aura-web[rabbitmq]

    Args:
        rabbitmq_url: AMQP connection URL.
        exchange_name: Topic exchange name for routing events.
    """

    def __init__(
        self,
        rabbitmq_url: str = "amqp://guest:guest@localhost/",
        *,
        exchange_name: str = "aura.events",
    ) -> None:
        self._url = rabbitmq_url
        self._exchange_name = exchange_name
        self._connection: Any = None
        self._channel: Any = None
        self._exchange: Any = None
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._message_handlers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._consumer_tags: dict[str, str] = {}
        self._queues: dict[str, Any] = {}
        self._running = False
        self._pending_replies: dict[str, asyncio.Future[Any]] = {}
        self._reply_queue: Any = None
        self._reply_consumer_tag: str | None = None

    async def _get_aio_pika(self) -> Any:
        try:
            import aio_pika
        except ImportError as exc:
            raise RuntimeError(
                "RabbitMQEventBus requires the 'aio-pika' package. "
                "Install with: pip install aura-web[rabbitmq]"
            ) from exc
        return aio_pika

    async def _ensure_connection(self) -> None:
        if self._connection is None:
            aio_pika = await self._get_aio_pika()
            self._connection = await aio_pika.connect_robust(self._url)
            self._channel = await self._connection.channel()
            self._exchange = await self._channel.declare_exchange(
                self._exchange_name,
                aio_pika.ExchangeType.TOPIC,
                durable=True,
            )

    @staticmethod
    def _encode_body(envelope: EventEnvelope) -> bytes:
        return json.dumps(
            {
                "event_id": envelope.event_id,
                "topic": envelope.topic,
                "timestamp": envelope.timestamp.isoformat(),
                "payload": envelope.payload,
            },
            default=str,
        ).encode()

    @staticmethod
    def _decode_envelope(topic: str, body: bytes) -> EventEnvelope:
        data = json.loads(body.decode())
        ts_raw = data.get("timestamp", "")
        timestamp = (
            datetime.fromisoformat(ts_raw)
            if ts_raw
            else datetime.now(tz=timezone.utc)
        )
        return EventEnvelope(
            topic=topic,
            payload=data.get("payload"),
            event_id=str(data.get("event_id", uuid.uuid4())),
            timestamp=timestamp,
        )

    async def publish(self, topic: str, payload: Any) -> EventEnvelope:
        await self._ensure_connection()
        aio_pika = await self._get_aio_pika()
        envelope = EventEnvelope(topic=topic, payload=payload)
        message = aio_pika.Message(
            body=self._encode_body(envelope),
            content_type="application/json",
        )
        await self._exchange.publish(message, routing_key=topic)
        return envelope

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)
        if self._running:
            await self._ensure_consumer(topic)

    async def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    async def register_message_handler(self, topic: str, handler: MessageHandler) -> None:
        """Register a request/response handler for *topic*."""
        if handler not in self._message_handlers[topic]:
            self._message_handlers[topic].append(handler)
        if self._running:
            await self._ensure_consumer(topic)

    async def request(self, topic: str, payload: Any, *, timeout: float = 30.0) -> Any:
        """Send a request and wait for a response on *topic*."""
        await self._ensure_connection()
        aio_pika = await self._get_aio_pika()
        await self._ensure_reply_consumer()

        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending_replies[correlation_id] = future

        envelope = EventEnvelope(topic=topic, payload=payload)
        message = aio_pika.Message(
            body=self._encode_body(envelope),
            reply_to=self._reply_queue.name,
            correlation_id=correlation_id,
            content_type="application/json",
        )
        await self._exchange.publish(message, routing_key=topic)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending_replies.pop(correlation_id, None)

    async def _ensure_reply_consumer(self) -> None:
        if self._reply_queue is not None:
            return
        await self._get_aio_pika()
        self._reply_queue = await self._channel.declare_queue(
            exclusive=True,
            auto_delete=True,
        )

        async def on_reply(message: Any) -> None:
            correlation_id = message.correlation_id
            if correlation_id and correlation_id in self._pending_replies:
                async with message.process():
                    data = json.loads(message.body.decode())
                    response = data.get("response", data)
                    future = self._pending_replies.get(correlation_id)
                    if future is not None and not future.done():
                        future.set_result(response)

        self._reply_consumer_tag = await self._reply_queue.consume(on_reply)

    async def _ensure_consumer(self, topic: str) -> None:
        if topic in self._consumer_tags:
            return
        await self._ensure_connection()
        aio_pika = await self._get_aio_pika()
        queue = await self._channel.declare_queue(exclusive=True, auto_delete=True)
        await queue.bind(self._exchange, routing_key=topic)

        async def on_message(message: Any) -> None:
            async with message.process():
                body = message.body
                reply_to = message.reply_to
                correlation_id = message.correlation_id

                if reply_to and self._message_handlers.get(topic):
                    data = json.loads(body.decode())
                    payload = data.get("payload", data)
                    for handler in list(self._message_handlers.get(topic, [])):
                        try:
                            result = await handler(payload)
                            response = aio_pika.Message(
                                body=json.dumps({"response": result}, default=str).encode(),
                                correlation_id=correlation_id,
                                content_type="application/json",
                            )
                            await self._channel.default_exchange.publish(
                                response,
                                routing_key=reply_to,
                            )
                        except Exception:
                            logger.exception(
                                "Error in message handler for topic %r", topic
                            )
                    return

                envelope = self._decode_envelope(topic, body)
                for handler in list(self._subscribers.get(topic, [])):
                    try:
                        await handler(envelope)
                    except Exception:
                        logger.exception(
                            "Error in event handler for topic %r", topic
                        )

        consumer_tag = await queue.consume(on_message)
        self._consumer_tags[topic] = consumer_tag
        self._queues[topic] = queue

    async def startup(self) -> None:
        self._running = True
        topics = set(self._subscribers.keys()) | set(self._message_handlers.keys())
        for topic in topics:
            await self._ensure_consumer(topic)

    async def shutdown(self) -> None:
        self._running = False
        if self._channel is not None:
            for tag in self._consumer_tags.values():
                await self._channel.cancel(tag)
            if self._reply_consumer_tag is not None:
                await self._channel.cancel(self._reply_consumer_tag)
        self._consumer_tags.clear()
        self._reply_consumer_tag = None
        self._reply_queue = None
        if self._connection is not None:
            await self._connection.close()
        self._connection = None
        self._channel = None
        self._exchange = None

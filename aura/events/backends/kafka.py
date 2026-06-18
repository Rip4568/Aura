"""Kafka event bus backend using aiokafka."""

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


class KafkaEventBus(EventBus):
    """Distributed event bus backed by Apache Kafka.

    Uses ``AIOKafkaProducer`` / ``AIOKafkaConsumer`` with manual commit
    after successful handler execution.

    Requires the ``kafka`` extra:

    .. code-block:: shell

        pip install aura-web[kafka]

    Args:
        bootstrap_servers: Kafka broker addresses.
        consumer_group: Consumer group id for subscribers.
        topic_prefix: Prefix applied to all topic names.
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        *,
        consumer_group: str = "aura",
        topic_prefix: str = "aura.",
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._consumer_group = consumer_group
        self._topic_prefix = topic_prefix
        self._producer: Any = None
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._message_handlers: dict[str, list[MessageHandler]] = defaultdict(list)
        self._consumer_tasks: dict[str, asyncio.Task[None]] = {}
        self._consumers: dict[str, Any] = {}
        self._running = False
        self._pending_replies: dict[str, asyncio.Future[Any]] = {}
        self._reply_consumer_task: asyncio.Task[None] | None = None
        self._reply_consumer: Any = None

    def _topic_name(self, topic: str) -> str:
        return f"{self._topic_prefix}{topic}"

    def _reply_topic(self) -> str:
        return f"{self._topic_prefix}reply.{self._consumer_group}"

    async def _get_aiokafka(self) -> Any:
        try:
            import aiokafka
        except ImportError as exc:
            raise RuntimeError(
                "KafkaEventBus requires the 'aiokafka' package. "
                "Install with: pip install aura-web[kafka]"
            ) from exc
        return aiokafka

    async def _ensure_producer(self) -> Any:
        if self._producer is None:
            aiokafka = await self._get_aiokafka()
            self._producer = aiokafka.AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
            )
            await self._producer.start()
        return self._producer

    @staticmethod
    def _encode_value(envelope: EventEnvelope) -> bytes:
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
    def _decode_envelope(topic: str, raw: bytes) -> EventEnvelope:
        data = json.loads(raw.decode())
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
        producer = await self._ensure_producer()
        envelope = EventEnvelope(topic=topic, payload=payload)
        await producer.send_and_wait(
            self._topic_name(topic),
            self._encode_value(envelope),
        )
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
        producer = await self._ensure_producer()
        await self._ensure_reply_consumer()

        correlation_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending_replies[correlation_id] = future

        envelope = EventEnvelope(topic=topic, payload=payload)
        headers = [
            ("correlation_id", correlation_id.encode()),
            ("reply_topic", self._reply_topic().encode()),
        ]
        await producer.send_and_wait(
            self._topic_name(topic),
            self._encode_value(envelope),
            headers=headers,
        )
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending_replies.pop(correlation_id, None)

    async def _ensure_reply_consumer(self) -> None:
        if self._reply_consumer_task is not None:
            return
        aiokafka = await self._get_aiokafka()
        self._reply_consumer = aiokafka.AIOKafkaConsumer(
            self._reply_topic(),
            bootstrap_servers=self._bootstrap_servers,
            group_id=f"{self._consumer_group}-reply",
            enable_auto_commit=False,
            auto_offset_reset="latest",
        )
        await self._reply_consumer.start()
        self._reply_consumer_task = asyncio.create_task(self._reply_loop())

    async def _reply_loop(self) -> None:
        consumer = self._reply_consumer
        while self._running or consumer is not None:
            try:
                records = await consumer.getmany(timeout_ms=500)
            except Exception:
                if not self._running:
                    break
                logger.exception("Kafka reply consumer error")
                await asyncio.sleep(1)
                continue

            for _tp, messages in records.items():
                for msg in messages:
                    correlation_id = None
                    for key, value in msg.headers or []:
                        if key == b"correlation_id" or key == "correlation_id":
                            correlation_id = value.decode() if isinstance(value, bytes) else value
                            break
                    if correlation_id and correlation_id in self._pending_replies:
                        data = json.loads(msg.value.decode())
                        response = data.get("response", data)
                        future = self._pending_replies.get(correlation_id)
                        if future is not None and not future.done():
                            future.set_result(response)
                    await consumer.commit()

    async def _ensure_consumer(self, topic: str) -> None:
        if topic in self._consumer_tasks:
            return
        aiokafka = await self._get_aiokafka()
        consumer = aiokafka.AIOKafkaConsumer(
            self._topic_name(topic),
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="latest",
        )
        await consumer.start()
        self._consumers[topic] = consumer
        self._consumer_tasks[topic] = asyncio.create_task(
            self._consumer_loop(topic, consumer)
        )

    async def _consumer_loop(self, topic: str, consumer: Any) -> None:
        while self._running:
            try:
                records = await consumer.getmany(timeout_ms=500)
            except Exception:
                if not self._running:
                    break
                logger.exception("Kafka consumer error for topic %r", topic)
                await asyncio.sleep(1)
                continue

            for _tp, messages in records.items():
                for msg in messages:
                    try:
                        await self._dispatch_message(topic, msg)
                    except Exception:
                        logger.exception(
                            "Error dispatching Kafka message on topic %r", topic
                        )
                    await consumer.commit()

    async def _dispatch_message(self, topic: str, msg: Any) -> None:
        headers = {k: v for k, v in (msg.headers or [])}
        correlation_id_raw = headers.get(b"correlation_id") or headers.get("correlation_id")
        reply_topic_raw = headers.get(b"reply_topic") or headers.get("reply_topic")

        correlation_id = (
            correlation_id_raw.decode()
            if isinstance(correlation_id_raw, bytes)
            else correlation_id_raw
        )
        reply_topic = (
            reply_topic_raw.decode()
            if isinstance(reply_topic_raw, bytes)
            else reply_topic_raw
        )

        if reply_topic and self._message_handlers.get(topic):
            data = json.loads(msg.value.decode())
            payload = data.get("payload", data)
            for handler in list(self._message_handlers.get(topic, [])):
                result = await handler(payload)
                producer = await self._ensure_producer()
                response_headers = [
                    ("correlation_id", (correlation_id or "").encode()),
                ]
                await producer.send_and_wait(
                    reply_topic,
                    json.dumps({"response": result}, default=str).encode(),
                    headers=response_headers,
                )
            return

        envelope = self._decode_envelope(topic, msg.value)
        for handler in list(self._subscribers.get(topic, [])):
            await handler(envelope)

    async def startup(self) -> None:
        self._running = True
        topics = set(self._subscribers.keys()) | set(self._message_handlers.keys())
        for topic in topics:
            await self._ensure_consumer(topic)

    async def shutdown(self) -> None:
        self._running = False
        for task in self._consumer_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._consumer_tasks.clear()

        for consumer in self._consumers.values():
            await consumer.stop()
        self._consumers.clear()

        if self._reply_consumer_task is not None:
            self._reply_consumer_task.cancel()
            try:
                await self._reply_consumer_task
            except asyncio.CancelledError:
                pass
            self._reply_consumer_task = None

        if self._reply_consumer is not None:
            await self._reply_consumer.stop()
            self._reply_consumer = None

        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

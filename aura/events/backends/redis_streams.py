"""Redis Streams event bus for distributed pub/sub."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from aura.events.base import EventBus, EventEnvelope, EventHandler

logger = logging.getLogger("aura.events")


class RedisStreamsEventBus(EventBus):
    """Distributed event bus backed by Redis Streams.

    Uses ``XADD`` for publishing and ``XREADGROUP`` for at-least-once
    consumption with fan-out to in-process subscribers.

    Requires the ``redis`` extra:

    .. code-block:: shell

        pip install aura-web[redis]

    Args:
        redis_url: Redis connection URL.
        stream_prefix: Prefix for stream keys (default ``aura:events:``).
        consumer_group: Redis consumer group name.
        consumer_name: Unique consumer name within the group.
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        *,
        stream_prefix: str = "aura:events:",
        consumer_group: str = "aura",
        consumer_name: str | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._stream_prefix = stream_prefix
        self._consumer_group = consumer_group
        self._consumer_name = consumer_name or f"aura-{uuid.uuid4().hex[:8]}"
        self._redis: Any = None
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)
        self._reader_tasks: dict[str, asyncio.Task[None]] = {}
        self._running = False

    def _stream_key(self, topic: str) -> str:
        return f"{self._stream_prefix}{topic}"

    async def _get_redis(self) -> Any:
        if self._redis is None:
            try:
                from redis.asyncio import Redis
            except ImportError as exc:
                raise RuntimeError(
                    "RedisStreamsEventBus requires the 'redis' package. "
                    "Install with: pip install aura-web[redis]"
                ) from exc
            self._redis = Redis.from_url(self._redis_url)
        return self._redis

    async def publish(self, topic: str, payload: Any) -> EventEnvelope:
        envelope = EventEnvelope(topic=topic, payload=payload)
        redis = await self._get_redis()
        stream_key = self._stream_key(topic)
        await redis.xadd(
            stream_key,
            {
                "event_id": envelope.event_id,
                "topic": envelope.topic,
                "timestamp": envelope.timestamp.isoformat(),
                "payload": json.dumps(payload, default=str),
            },
        )
        return envelope

    async def subscribe(self, topic: str, handler: EventHandler) -> None:
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)
        if self._running:
            await self._ensure_reader(topic)

    async def unsubscribe(self, topic: str, handler: EventHandler) -> None:
        handlers = self._subscribers.get(topic, [])
        if handler in handlers:
            handlers.remove(handler)

    async def startup(self) -> None:
        self._running = True
        for topic in list(self._subscribers.keys()):
            await self._ensure_reader(topic)

    async def shutdown(self) -> None:
        self._running = False
        for task in self._reader_tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._reader_tasks.clear()
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    async def _ensure_reader(self, topic: str) -> None:
        if topic in self._reader_tasks:
            return
        redis = await self._get_redis()
        stream_key = self._stream_key(topic)
        try:
            await redis.xgroup_create(stream_key, self._consumer_group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                logger.debug("xgroup_create for %s: %s", stream_key, exc)
        self._reader_tasks[topic] = asyncio.create_task(self._reader_loop(topic))

    async def _reader_loop(self, topic: str) -> None:
        redis = await self._get_redis()
        stream_key = self._stream_key(topic)
        while self._running:
            try:
                messages = await redis.xreadgroup(
                    self._consumer_group,
                    self._consumer_name,
                    {stream_key: ">"},
                    count=10,
                    block=1000,
                )
            except Exception:
                logger.exception("Redis xreadgroup failed for topic %r", topic)
                await asyncio.sleep(1)
                continue

            if not messages:
                continue

            for _stream, entries in messages:
                for message_id, fields in entries:
                    envelope = self._decode_envelope(topic, fields)
                    for handler in list(self._subscribers.get(topic, [])):
                        try:
                            await handler(envelope)
                        except Exception:
                            logger.exception(
                                "Error in event handler for topic %r", topic
                            )
                    await redis.xack(stream_key, self._consumer_group, message_id)

    @staticmethod
    def _decode_envelope(topic: str, fields: dict[Any, Any]) -> EventEnvelope:
        raw_payload = fields.get(b"payload") or fields.get("payload") or b"null"
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode()
        payload = json.loads(raw_payload)

        event_id = fields.get(b"event_id") or fields.get("event_id") or ""
        if isinstance(event_id, bytes):
            event_id = event_id.decode()

        ts_raw = fields.get(b"timestamp") or fields.get("timestamp") or ""
        if isinstance(ts_raw, bytes):
            ts_raw = ts_raw.decode()
        timestamp = (
            datetime.fromisoformat(ts_raw)
            if ts_raw
            else datetime.now(tz=timezone.utc)
        )

        return EventEnvelope(
            topic=topic,
            payload=payload,
            event_id=str(event_id) or str(uuid.uuid4()),
            timestamp=timestamp,
        )

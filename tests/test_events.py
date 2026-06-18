"""Tests for the Aura event bus subsystem."""

from __future__ import annotations

import asyncio
import importlib.util
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.events import EventEnvelope, EventHandlerRegistry, InMemoryEventBus, on_event
from aura.events.decorators import get_event_bus, set_event_bus
from aura.events.lifecycle import ensure_events_started, reset_events_lifecycle
from aura.modules.base import Module

redis_installed = importlib.util.find_spec("redis") is not None


@pytest.fixture(autouse=True)
def reset_event_state() -> Generator[None, None, None]:
    """Isolate event registry and global bus between tests."""
    EventHandlerRegistry.clear()
    set_event_bus(None)
    reset_events_lifecycle()
    yield
    EventHandlerRegistry.clear()
    set_event_bus(None)
    reset_events_lifecycle()


class TestInMemoryEventBus:
    @pytest.mark.asyncio
    async def test_publish_subscribe(self) -> None:
        bus = InMemoryEventBus()
        await bus.startup()
        received: list[EventEnvelope] = []

        async def handler(event: EventEnvelope) -> None:
            received.append(event)

        await bus.subscribe("user.created", handler)
        envelope = await bus.publish("user.created", {"id": 42})

        await asyncio.sleep(0.05)
        assert len(received) == 1
        assert received[0].event_id == envelope.event_id
        assert received[0].payload == {"id": 42}
        assert received[0].topic == "user.created"
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_subscribers_same_topic(self) -> None:
        bus = InMemoryEventBus()
        await bus.startup()
        first: list[EventEnvelope] = []
        second: list[EventEnvelope] = []

        async def handler_a(event: EventEnvelope) -> None:
            first.append(event)

        async def handler_b(event: EventEnvelope) -> None:
            second.append(event)

        await bus.subscribe("order.placed", handler_a)
        await bus.subscribe("order.placed", handler_b)
        await bus.publish("order.placed", {"order_id": 7})

        await asyncio.sleep(0.05)
        assert len(first) == 1
        assert len(second) == 1
        assert first[0].payload == second[0].payload
        await bus.shutdown()


class TestOnEventDecorator:
    @pytest.mark.asyncio
    async def test_handler_registration_via_decorator(self) -> None:
        bus = InMemoryEventBus()
        await bus.startup()
        captured: list[Any] = []

        @on_event("email.sent")
        async def handle_email(event: EventEnvelope) -> None:
            captured.append(event.payload)

        handlers = EventHandlerRegistry.get("email.sent")
        assert len(handlers) == 1
        assert handlers[0].name.endswith("handle_email")

        await bus.subscribe("email.sent", handle_email)
        await bus.publish("email.sent", {"to": "a@b.com"})

        await asyncio.sleep(0.05)
        assert captured == [{"to": "a@b.com"}]
        await bus.shutdown()

    def test_controller_method_wiring(self) -> None:
        import asyncio

        from aura.di.container import DIContainer, Lifetime
        from aura.di.decorators import injectable
        from aura.modules.registry import ModuleRegistry

        received: list[EventEnvelope] = []

        @injectable(lifetime=Lifetime.SINGLETON)
        class NotificationService:
            @on_event("user.created")
            async def on_user_created(self, event: EventEnvelope) -> None:
                received.append(event)

        @Module(providers=[NotificationService])
        class AppModule:
            pass

        container = DIContainer()
        registry = ModuleRegistry(container)
        registry.register(AppModule)

        bus = InMemoryEventBus()
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(
                ensure_events_started(
                    container=container,
                    registry=registry,
                    bus=bus,
                )
            )
            loop.run_until_complete(bus.publish("user.created", {"id": 1}))
            loop.run_until_complete(asyncio.sleep(0.05))
        finally:
            loop.close()

        assert get_event_bus() is bus
        assert len(received) == 1
        assert received[0].payload == {"id": 1}


class TestEnsureEventsStarted:
    @pytest.mark.asyncio
    async def test_idempotent_startup(self) -> None:
        from aura.config.base import EventsConfig
        from aura.di.container import DIContainer
        from aura.modules.registry import ModuleRegistry

        container = DIContainer()
        registry = ModuleRegistry(container)
        container._app_registry = registry  # type: ignore[attr-defined]

        cfg = EventsConfig(enabled=True, backend="memory")
        bus = await ensure_events_started(
            container=container,
            registry=registry,
            events_config=cfg,
        )
        assert bus is not None
        again = await ensure_events_started(
            container=container,
            registry=registry,
            events_config=cfg,
        )
        assert again is bus


@pytest.mark.skipif(not redis_installed, reason="redis package not installed")
class TestRedisStreamsEventBus:
    @pytest.mark.asyncio
    async def test_redis_streams_lazy_import(self) -> None:
        from aura.events.backends.redis_streams import RedisStreamsEventBus

        assert RedisStreamsEventBus is not None

    @pytest.mark.asyncio
    async def test_redis_streams_publish_without_server(self) -> None:
        from aura.events.backends.redis_streams import RedisStreamsEventBus

        bus = RedisStreamsEventBus(redis_url="redis://127.0.0.1:16379")
        with pytest.raises(Exception):
            await bus.publish("test.topic", {"x": 1})
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_redis_streams_publish_uses_xadd(self) -> None:
        from aura.events.backends.redis_streams import RedisStreamsEventBus

        mock_redis = MagicMock()
        mock_redis.xadd = AsyncMock(return_value=b"1-0")
        mock_redis.aclose = AsyncMock()

        with patch("redis.asyncio.Redis.from_url", return_value=mock_redis):
            bus = RedisStreamsEventBus(stream_prefix="aura:events:")
            envelope = await bus.publish("user.created", {"id": 1})

        assert envelope.topic == "user.created"
        mock_redis.xadd.assert_awaited_once()
        call_args = mock_redis.xadd.await_args
        assert call_args is not None
        stream_key = call_args.args[0]
        assert stream_key == "aura:events:user.created"
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_create_event_bus_from_config(self) -> None:
        from aura.config.base import EventsConfig
        from aura.events.wiring import create_event_bus_from_config

        cfg = EventsConfig(backend="redis_streams")
        bus = create_event_bus_from_config(cfg)
        from aura.events.backends.redis_streams import RedisStreamsEventBus

        assert isinstance(bus, RedisStreamsEventBus)
        await bus.shutdown()


class TestEventsConfig:
    def test_events_config_defaults(self) -> None:
        from aura.config.base import AuraConfig, EventsConfig

        events = EventsConfig()
        assert events.enabled is False
        assert events.backend == "memory"
        assert events.stream_prefix == "aura:events:"
        assert events.rabbitmq_url == "amqp://guest:guest@localhost/"
        assert events.kafka_bootstrap_servers == "localhost:9092"
        assert events.kafka_consumer_group == "aura"

        cfg = AuraConfig()
        assert cfg.events.enabled is False

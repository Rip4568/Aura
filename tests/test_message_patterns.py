"""Tests for @EventPattern / @MessagePattern and MessagingClient."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock

import pytest

from aura.events import EventPattern, MessagePattern, MessagingClient
from aura.events.backends.memory import InMemoryEventBus
from aura.events.decorators import set_event_bus
from aura.events.lifecycle import reset_events_lifecycle
from aura.events.microservice import MessageHandlerRegistry


@pytest.fixture(autouse=True)
def reset_message_state() -> Generator[None, None, None]:
    """Isolate message registry between tests."""
    MessageHandlerRegistry.clear()
    set_event_bus(None)
    reset_events_lifecycle()
    yield
    MessageHandlerRegistry.clear()
    set_event_bus(None)
    reset_events_lifecycle()


class TestEventPatternDecorator:
    def test_registers_metadata(self) -> None:
        @EventPattern("order.placed")
        async def on_order(data: dict[str, Any]) -> None:
            pass

        meta = on_order.__aura_message__  # type: ignore[attr-defined]
        assert meta["topic"] == "order.placed"
        assert meta["pattern"] == "event"
        assert meta["name"] == f"{on_order.__module__}.{on_order.__qualname__}"

    def test_registers_in_global_registry(self) -> None:
        @EventPattern("user.created")
        async def handle_user(data: dict[str, Any]) -> None:
            pass

        handlers = MessageHandlerRegistry.get("user.created")
        assert len(handlers) == 1
        assert handlers[0].pattern == "event"
        assert handlers[0].func is handle_user


class TestMessagePatternDecorator:
    def test_registers_metadata(self) -> None:
        @MessagePattern("math.sum")
        async def sum_numbers(data: dict[str, int]) -> dict[str, int]:
            return {"result": data["a"] + data["b"]}

        meta = sum_numbers.__aura_message__  # type: ignore[attr-defined]
        assert meta["topic"] == "math.sum"
        assert meta["pattern"] == "message"
        assert meta["name"] == f"{sum_numbers.__module__}.{sum_numbers.__qualname__}"

    def test_registers_in_global_registry(self) -> None:
        @MessagePattern("ping")
        async def ping_handler(data: dict[str, str]) -> dict[str, str]:
            return {"pong": data["msg"]}

        handlers = MessageHandlerRegistry.get("ping")
        assert len(handlers) == 1
        assert handlers[0].pattern == "message"


class TestMessagingClient:
    @pytest.mark.asyncio
    async def test_emit_publishes_event(self) -> None:
        bus = InMemoryEventBus()
        await bus.startup()
        received: list[Any] = []

        async def handler(event: Any) -> None:
            received.append(event.payload)

        await bus.subscribe("notify", handler)
        client = MessagingClient(bus)
        envelope = await client.emit("notify", {"msg": "hello"})

        await asyncio.sleep(0.05)
        assert envelope.topic == "notify"
        assert received == [{"msg": "hello"}]
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_send_uses_request_on_supported_backend(self) -> None:
        bus = InMemoryEventBus()
        bus.request = AsyncMock(return_value={"ok": True})  # type: ignore[attr-defined]
        client = MessagingClient(bus)

        result = await client.send("rpc.topic", {"x": 1})
        assert result == {"ok": True}
        bus.request.assert_awaited_once_with("rpc.topic", {"x": 1}, timeout=30.0)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_send_raises_on_unsupported_backend(self) -> None:
        bus = InMemoryEventBus()
        client = MessagingClient(bus)

        with pytest.raises(RuntimeError, match="not supported"):
            await client.send("rpc.topic", {"x": 1})


class TestMessagePatternWiring:
    @pytest.mark.asyncio
    async def test_event_pattern_wiring_on_memory_bus(self) -> None:
        from aura.di.container import DIContainer, Lifetime
        from aura.di.decorators import injectable
        from aura.events.wiring import wire_event_handlers
        from aura.modules.base import Module
        from aura.modules.registry import ModuleRegistry

        captured: list[Any] = []

        @injectable(lifetime=Lifetime.SINGLETON)
        class EventsController:
            @EventPattern("item.added")
            async def on_item(self, data: dict[str, int]) -> None:
                captured.append(data)

        @Module(controllers=[EventsController])
        class AppModule:
            pass

        container = DIContainer()
        registry = ModuleRegistry(container)
        registry.register(AppModule)

        bus = InMemoryEventBus()
        await wire_event_handlers(bus, registry, container)
        await bus.startup()
        await bus.publish("item.added", {"id": 99})

        await asyncio.sleep(0.05)
        assert captured == [{"id": 99}]
        await bus.shutdown()

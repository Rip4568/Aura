"""Tests for RabbitMQ event bus backend."""

from __future__ import annotations

import importlib.util
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.events.backends.rabbitmq import RabbitMQEventBus

aio_pika_installed = importlib.util.find_spec("aio_pika") is not None


def _make_mock_aio_pika() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Build a minimal aio-pika mock hierarchy."""
    mock_exchange = MagicMock()
    mock_exchange.publish = AsyncMock()

    mock_channel = MagicMock()
    mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
    mock_channel.declare_queue = AsyncMock()
    mock_channel.cancel = AsyncMock()
    mock_channel.default_exchange = MagicMock()
    mock_channel.default_exchange.publish = AsyncMock()

    mock_connection = MagicMock()
    mock_connection.channel = AsyncMock(return_value=mock_channel)
    mock_connection.close = AsyncMock()

    mock_aio_pika = MagicMock()
    mock_aio_pika.connect_robust = AsyncMock(return_value=mock_connection)
    mock_aio_pika.ExchangeType = MagicMock()
    mock_aio_pika.ExchangeType.TOPIC = "topic"
    mock_aio_pika.Message = MagicMock(side_effect=lambda **kw: MagicMock(**kw))

    return mock_aio_pika, mock_connection, mock_channel, mock_exchange


@pytest.mark.skipif(not aio_pika_installed, reason="aio-pika package not installed")
class TestRabbitMQEventBusInstalled:
    def test_module_importable(self) -> None:
        from aura.events.backends.rabbitmq import RabbitMQEventBus as Bus

        assert Bus is not None


class TestRabbitMQEventBusMocked:
    @pytest.mark.asyncio
    async def test_lazy_import_error_without_aio_pika(self) -> None:
        bus = RabbitMQEventBus()
        with patch.dict("sys.modules", {"aio_pika": None}):
            with patch(
                "aura.events.backends.rabbitmq.RabbitMQEventBus._get_aio_pika",
                side_effect=RuntimeError("Install with: pip install aura-web[rabbitmq]"),
            ):
                with pytest.raises(RuntimeError, match="rabbitmq"):
                    await bus.publish("test", {"x": 1})

    @pytest.mark.asyncio
    async def test_publish_uses_topic_exchange(self) -> None:
        mock_aio_pika, _conn, _channel, mock_exchange = _make_mock_aio_pika()
        bus = RabbitMQEventBus(rabbitmq_url="amqp://guest:guest@localhost/")

        with patch.object(
            bus, "_get_aio_pika", AsyncMock(return_value=mock_aio_pika)
        ):
            envelope = await bus.publish("user.created", {"id": 1})

        assert envelope.topic == "user.created"
        assert envelope.payload == {"id": 1}
        mock_aio_pika.connect_robust.assert_awaited_once_with(
            "amqp://guest:guest@localhost/"
        )
        mock_exchange.publish.assert_awaited_once()
        call_kwargs = mock_exchange.publish.await_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("routing_key") == "user.created"
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_create_event_bus_from_config(self) -> None:
        from aura.config.base import EventsConfig
        from aura.events.wiring import create_event_bus_from_config

        cfg = EventsConfig(backend="rabbitmq", rabbitmq_url="amqp://test/")
        bus = create_event_bus_from_config(cfg)
        assert isinstance(bus, RabbitMQEventBus)
        assert bus._url == "amqp://test/"  # noqa: SLF001
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_register_message_handler(self) -> None:
        mock_aio_pika, _conn, mock_channel, _exchange = _make_mock_aio_pika()
        mock_queue = MagicMock()
        mock_queue.bind = AsyncMock()
        mock_queue.consume = AsyncMock(return_value="tag-1")
        mock_channel.declare_queue = AsyncMock(return_value=mock_queue)

        bus = RabbitMQEventBus()
        handled: list[Any] = []

        async def handler(payload: dict[str, int]) -> dict[str, int]:
            handled.append(payload)
            return {"sum": payload["a"] + payload["b"]}

        with patch.object(
            bus, "_get_aio_pika", AsyncMock(return_value=mock_aio_pika)
        ):
            await bus.register_message_handler("math.sum", handler)
            await bus.startup()

        assert "math.sum" in bus._message_handlers  # noqa: SLF001
        await bus.shutdown()

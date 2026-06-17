"""Tests for Kafka event bus backend."""

from __future__ import annotations

import importlib.util
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.events.backends.kafka import KafkaEventBus

aiokafka_installed = importlib.util.find_spec("aiokafka") is not None


def _make_mock_aiokafka() -> tuple[MagicMock, MagicMock]:
    """Build minimal aiokafka producer/consumer mocks."""
    mock_producer = MagicMock()
    mock_producer.start = AsyncMock()
    mock_producer.stop = AsyncMock()
    mock_producer.send_and_wait = AsyncMock()

    mock_consumer = MagicMock()
    mock_consumer.start = AsyncMock()
    mock_consumer.stop = AsyncMock()
    mock_consumer.getmany = AsyncMock(return_value={})
    mock_consumer.commit = AsyncMock()

    mock_aiokafka = MagicMock()
    mock_aiokafka.AIOKafkaProducer = MagicMock(return_value=mock_producer)
    mock_aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

    return mock_aiokafka, mock_producer


@pytest.mark.skipif(not aiokafka_installed, reason="aiokafka package not installed")
class TestKafkaEventBusInstalled:
    def test_module_importable(self) -> None:
        from aura.events.backends.kafka import KafkaEventBus as Bus

        assert Bus is not None


class TestKafkaEventBusMocked:
    @pytest.mark.asyncio
    async def test_lazy_import_error_without_aiokafka(self) -> None:
        bus = KafkaEventBus()
        with patch(
            "aura.events.backends.kafka.KafkaEventBus._get_aiokafka",
            side_effect=RuntimeError("Install with: pip install aura-web[kafka]"),
        ):
            with pytest.raises(RuntimeError, match="kafka"):
                await bus.publish("test", {"x": 1})

    @pytest.mark.asyncio
    async def test_publish_sends_to_prefixed_topic(self) -> None:
        mock_aiokafka, mock_producer = _make_mock_aiokafka()
        bus = KafkaEventBus(
            bootstrap_servers="localhost:9092",
            consumer_group="aura-test",
        )

        with patch.object(
            bus, "_get_aiokafka", AsyncMock(return_value=mock_aiokafka)
        ):
            envelope = await bus.publish("user.created", {"id": 1})

        assert envelope.topic == "user.created"
        mock_producer.send_and_wait.assert_awaited_once()
        call_args = mock_producer.send_and_wait.await_args
        assert call_args is not None
        assert call_args.args[0] == "aura.user.created"
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_create_event_bus_from_config(self) -> None:
        from aura.config.base import EventsConfig
        from aura.events.wiring import create_event_bus_from_config

        cfg = EventsConfig(
            backend="kafka",
            kafka_bootstrap_servers="broker:9092",
            kafka_consumer_group="my-group",
        )
        bus = create_event_bus_from_config(cfg)
        assert isinstance(bus, KafkaEventBus)
        assert bus._bootstrap_servers == "broker:9092"  # noqa: SLF001
        assert bus._consumer_group == "my-group"  # noqa: SLF001
        await bus.shutdown()

    @pytest.mark.asyncio
    async def test_register_message_handler(self) -> None:
        mock_aiokafka, _producer = _make_mock_aiokafka()
        bus = KafkaEventBus()

        async def handler(payload: dict[str, int]) -> dict[str, int]:
            return {"result": payload["n"] * 2}

        with patch.object(
            bus, "_get_aiokafka", AsyncMock(return_value=mock_aiokafka)
        ):
            await bus.register_message_handler("math.double", handler)
            await bus.startup()

        assert "math.double" in bus._message_handlers  # noqa: SLF001
        await bus.shutdown()

"""Tests for SAQ backend integration."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aura.jobs.backends.saq_backend import SAQBackend
from aura.jobs.base import TaskDefinition, TaskStatus


@pytest.mark.asyncio
async def test_saq_backend_startup_uses_from_url() -> None:
    backend = SAQBackend(redis_url="redis://localhost:6379/0", queue_name="emails")
    mock_queue = MagicMock()
    mock_queue.disconnect = AsyncMock()

    mock_queue_cls = MagicMock()
    mock_queue_cls.from_url = MagicMock(return_value=mock_queue)
    mock_saq = MagicMock()
    mock_saq.Queue = mock_queue_cls

    with patch.dict(sys.modules, {"saq": mock_saq}):
        await backend.startup()

    mock_queue_cls.from_url.assert_called_once_with(
        "redis://localhost:6379/0", name="emails"
    )
    assert backend._queue is mock_queue


@pytest.mark.asyncio
async def test_saq_backend_enqueue_uses_seconds_not_milliseconds() -> None:
    async def sample_task(**kwargs: object) -> str:
        return "ok"

    task = TaskDefinition(name="sample_task", func=sample_task, timeout=30, retry=2)
    backend = SAQBackend()
    mock_queue = MagicMock()
    mock_queue.enqueue = AsyncMock()
    backend._queue = mock_queue

    with patch("time.time", return_value=1_700_000_000.0):
        result = await backend.enqueue(task, kwargs={"user_id": 1}, delay=10)

    assert result.status == TaskStatus.PENDING
    mock_queue.enqueue.assert_awaited_once()
    _, kwargs = mock_queue.enqueue.await_args
    assert kwargs["key"] == result.task_id
    assert kwargs["timeout"] == 30
    assert kwargs["retries"] == 2
    assert kwargs["scheduled"] == 1_700_000_010
    assert kwargs["user_id"] == 1


@pytest.mark.asyncio
async def test_saq_backend_get_result_maps_status() -> None:
    backend = SAQBackend()
    job = MagicMock()
    job.status = "complete"
    job.result = {"ok": True}
    job.error = None
    job.started = 1_700_000_000
    job.completed = 1_700_000_001

    mock_queue = MagicMock()
    mock_queue.job = AsyncMock(return_value=job)
    backend._queue = mock_queue

    result = await backend.get_result("job-1")
    assert result is not None
    assert result.status == TaskStatus.SUCCESS
    assert result.result == {"ok": True}

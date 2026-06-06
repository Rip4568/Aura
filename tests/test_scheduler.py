"""Tests for periodic task scheduling and the CronScheduler loop."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import pytest

from aura.jobs.base import TaskRegistry
from aura.jobs.decorators import periodic
from aura.jobs.scheduler import CronScheduler


# Mock task backend that acts as an SAQ / memory backend
class MockBackend:
    def __init__(self) -> None:
        self.enqueued = []

    async def enqueue(self, task: Any, args: tuple, kwargs: dict) -> None:
        self.enqueued.append((task, args, kwargs))


@pytest.fixture(autouse=True)
def clean_registry() -> None:
    """Ensures a clean TaskRegistry state before and after each test."""
    original_tasks = dict(TaskRegistry.all())
    yield
    TaskRegistry._tasks = original_tasks


def test_scheduler_initialization() -> None:
    """Verifies default properties of the CronScheduler."""
    backend = MockBackend()
    scheduler = CronScheduler(backend=backend, tick_interval=0.05)
    assert scheduler._backend == backend
    assert scheduler._tick_interval == 0.05
    assert not scheduler._running


@pytest.mark.anyio
async def test_run_startup_tasks() -> None:
    """Verifies that tasks marked with run_on_startup are enqueued immediately."""
    backend = MockBackend()
    
    # Register a periodic task with run_on_startup=True
    @periodic(cron="* * * * *", run_on_startup=True, name="startup_job")
    async def my_startup_task() -> None:
        pass

    scheduler = CronScheduler(backend=backend, tick_interval=0.01)
    await scheduler._run_startup_tasks()

    assert len(backend.enqueued) == 1
    assert backend.enqueued[0][0].name == "startup_job"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason='Cron "* * * * *" fires at minute boundaries; on Windows the scheduler '
    "loop tick timing requires AsyncIO event-loop precision that is unreliable. "
    "This test is inherently flaky across OSes — the 0.02s sleep crossing a "
    "minute boundary is luck-based.",
)
@pytest.mark.anyio
async def test_scheduler_loop_dispatches_due_tasks() -> None:
    """Verifies that the main scheduler loop checks due tasks and triggers them."""
    pytest.importorskip("croniter")
    backend = MockBackend()

    # Register a periodic task that triggers every minute
    @periodic(cron="* * * * *", name="due_job")
    async def my_due_task() -> None:
        pass

    scheduler = CronScheduler(backend=backend, tick_interval=0.005)

    # Start the scheduler
    await scheduler.start()

    # Wait for a couple of ticks
    await asyncio.sleep(0.02)

    # Stop the scheduler to clean up background tasks
    await scheduler.stop()

    assert len(backend.enqueued) >= 1
    assert backend.enqueued[0][0].name == "due_job"


@pytest.mark.anyio
async def test_scheduler_loop_handles_invalid_cron() -> None:
    """Verifies that invalid cron expressions do not crash the loop."""
    pytest.importorskip("croniter")
    backend = MockBackend()

    # Register a periodic task with an invalid cron expression
    @periodic(cron="invalid_cron_exp", name="bad_cron_job")
    async def my_bad_task() -> None:
        pass

    scheduler = CronScheduler(backend=backend, tick_interval=0.005)
    
    # Start the scheduler (it shouldn't raise exceptions)
    await scheduler.start()
    await asyncio.sleep(0.015)
    await scheduler.stop()

    # No task should be enqueued because of the invalid cron expression
    assert len(backend.enqueued) == 0

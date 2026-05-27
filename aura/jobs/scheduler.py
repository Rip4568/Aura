"""Cron-based periodic task scheduler for Aura."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class CronScheduler:
    """Runs periodic tasks according to their cron expressions.

    The scheduler inspects the :class:`~aura.jobs.base.TaskRegistry` for tasks
    decorated with :func:`~aura.jobs.decorators.periodic` and triggers them on
    schedule.

    Requires ``croniter`` to be installed::

        pip install croniter

    Args:
        backend: The task backend used to enqueue scheduled jobs.
        tick_interval: How often (seconds) the scheduler checks for due tasks.

    Example::

        scheduler = CronScheduler(backend=memory_backend)
        await scheduler.start()
        # …
        await scheduler.stop()
    """

    def __init__(self, backend: Any, tick_interval: float = 10.0) -> None:
        self._backend = backend
        self._tick_interval = tick_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the scheduler background loop."""
        self._running = True
        await self._run_startup_tasks()
        self._task = asyncio.create_task(self._loop())
        logger.info("CronScheduler started (tick=%.1fs)", self._tick_interval)

    async def stop(self) -> None:
        """Stop the scheduler and await the background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("CronScheduler stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_startup_tasks(self) -> None:
        """Enqueue any periodic tasks marked with run_on_startup=True."""
        from aura.jobs.base import TaskRegistry
        from aura.jobs.decorators import PeriodicTaskDefinition

        for task_def in TaskRegistry.all().values():
            if isinstance(task_def, PeriodicTaskDefinition) and task_def.run_on_startup:
                logger.info("Running startup task: %s", task_def.name)
                await self._backend.enqueue(task=task_def, args=(), kwargs={})

    async def _loop(self) -> None:
        """Main scheduler tick loop."""
        try:
            import croniter  # type: ignore[import]
        except ImportError:
            logger.warning(
                "croniter is not installed — periodic tasks will not be scheduled. "
                "Install with: pip install croniter"
            )
            return

        from aura.jobs.base import TaskRegistry
        from aura.jobs.decorators import PeriodicTaskDefinition

        # Track last-fired time per task to avoid duplicate dispatches
        last_fired: dict[str, datetime] = {}

        while self._running:
            now = datetime.now(tz=timezone.utc)

            for task_def in TaskRegistry.all().values():
                if not isinstance(task_def, PeriodicTaskDefinition) or not task_def.cron:
                    continue

                try:
                    cron = croniter.croniter(task_def.cron, last_fired.get(task_def.name, now))
                    next_run: datetime = cron.get_next(datetime)
                except Exception:  # noqa: BLE001
                    logger.exception("Invalid cron expression for task %s", task_def.name)
                    continue

                if next_run <= now:
                    logger.debug("Dispatching periodic task: %s", task_def.name)
                    try:
                        await self._backend.enqueue(task=task_def, args=(), kwargs={})
                    except Exception:  # noqa: BLE001
                        logger.exception("Failed to enqueue periodic task: %s", task_def.name)
                    last_fired[task_def.name] = now

            await asyncio.sleep(self._tick_interval)

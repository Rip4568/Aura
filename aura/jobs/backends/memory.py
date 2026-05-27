"""In-memory task queue backend for development and testing."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from aura.jobs.base import TaskDefinition, TaskResult, TaskStatus
from aura.jobs.backends.base import TaskBackend


class MemoryBackend(TaskBackend):
    """In-memory task backend that executes jobs asynchronously via asyncio.

    Tasks are placed on an asyncio.Queue and processed by a background worker
    coroutine.  Results are kept in memory for later retrieval.

    This backend is intended for development, testing, and simple deployments
    that do not require persistent queues.

    Example::

        backend = MemoryBackend()
        await backend.startup()

        result = await backend.enqueue(task_def, kwargs={"user_id": 1})
        # result.status == TaskStatus.PENDING initially

        # poll until complete
        final = await backend.get_result(result.task_id)
    """

    def __init__(self, concurrency: int = 4) -> None:
        self._concurrency = concurrency
        self._queue: asyncio.Queue[tuple[str, TaskDefinition, tuple[Any, ...], dict[str, Any], int]] = asyncio.Queue()
        self._results: dict[str, TaskResult] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._running = False

    async def startup(self) -> None:
        """Start background worker tasks."""
        self._running = True
        for _ in range(self._concurrency):
            worker = asyncio.create_task(self._worker_loop())
            self._workers.append(worker)

    async def shutdown(self) -> None:
        """Stop all worker tasks gracefully."""
        self._running = False
        # Send sentinel values to unblock workers
        for _ in self._workers:
            await self._queue.put(("__stop__", None, (), {}, 0))  # type: ignore[arg-type]
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(
        self,
        task: TaskDefinition,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        delay: int = 0,
    ) -> TaskResult:
        """Enqueue a task for execution.

        Args:
            task: The task definition to execute.
            args: Positional arguments for the task function.
            kwargs: Keyword arguments for the task function.
            delay: Seconds to wait before executing (0 = immediate).

        Returns:
            A TaskResult with PENDING status and a unique task_id.
        """
        task_id = str(uuid.uuid4())
        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
        )
        self._results[task_id] = result

        if delay > 0:
            # Schedule delayed execution without blocking the caller
            asyncio.create_task(self._delayed_enqueue(task_id, task, args, kwargs or {}, delay))
        else:
            await self._queue.put((task_id, task, args, kwargs or {}, 0))

        return result

    async def get_result(self, task_id: str) -> TaskResult | None:
        """Retrieve a task result by its ID.

        Args:
            task_id: The unique task identifier.

        Returns:
            The stored TaskResult, or None if not found.
        """
        return self._results.get(task_id)

    async def wait_for_result(
        self,
        task_id: str,
        timeout: float = 30.0,
        poll_interval: float = 0.05,
    ) -> TaskResult | None:
        """Poll until the task completes or timeout is reached.

        Args:
            task_id: The task to wait for.
            timeout: Maximum seconds to wait.
            poll_interval: Seconds between polls.

        Returns:
            The final TaskResult, or None if timed out.
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            result = self._results.get(task_id)
            if result and result.status in (
                TaskStatus.SUCCESS,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED,
            ):
                return result
            await asyncio.sleep(poll_interval)
        return self._results.get(task_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _delayed_enqueue(
        self,
        task_id: str,
        task: TaskDefinition,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        delay: int,
    ) -> None:
        """Wait for *delay* seconds then place the task on the queue."""
        await asyncio.sleep(delay)
        await self._queue.put((task_id, task, args, kwargs, 0))

    async def _worker_loop(self) -> None:
        """Consume tasks from the queue and execute them."""
        while True:
            item = await self._queue.get()
            task_id, task_def, args, kwargs, _ = item

            # Sentinel stop signal
            if task_id == "__stop__":
                self._queue.task_done()
                break

            try:
                await self._execute(task_id, task_def, args, kwargs)
            finally:
                self._queue.task_done()

    async def _execute(
        self,
        task_id: str,
        task_def: TaskDefinition,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """Execute a single task, respecting retry and timeout settings."""
        result = self._results[task_id]
        result.status = TaskStatus.RUNNING
        result.started_at = datetime.now(tz=timezone.utc)

        attempts = 0
        max_attempts = task_def.retry + 1

        while attempts < max_attempts:
            try:
                coro = task_def.func(*args, **kwargs)
                if task_def.timeout is not None:
                    raw = await asyncio.wait_for(coro, timeout=task_def.timeout)
                else:
                    raw = await coro

                result.result = raw
                result.status = TaskStatus.SUCCESS
                result.completed_at = datetime.now(tz=timezone.utc)
                return

            except asyncio.TimeoutError:
                attempts += 1
                result.error = f"Task timed out after {task_def.timeout}s"
                if attempts < max_attempts:
                    result.status = TaskStatus.RETRYING
                else:
                    result.status = TaskStatus.FAILED
                    result.completed_at = datetime.now(tz=timezone.utc)

            except Exception as exc:  # noqa: BLE001
                attempts += 1
                result.error = f"{type(exc).__name__}: {exc}"
                if attempts < max_attempts:
                    result.status = TaskStatus.RETRYING
                else:
                    result.status = TaskStatus.FAILED
                    result.completed_at = datetime.now(tz=timezone.utc)

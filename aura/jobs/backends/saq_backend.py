"""SAQ (Simple Async Queue) backend integration for Aura."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from aura.jobs.backends.base import TaskBackend
from aura.jobs.base import TaskDefinition, TaskResult, TaskStatus


class SAQBackend(TaskBackend):
    """Task backend powered by SAQ (Simple Async Queue) with Redis.

    Requires ``saq`` and ``redis`` extras:

    .. code-block:: shell

        pip install aura-framework[saq,redis]

    Args:
        redis_url: Redis connection URL (default: ``redis://localhost:6379``).
        queue_name: Default SAQ queue name.

    Example::

        backend = SAQBackend(redis_url="redis://localhost:6379")
        await backend.startup()
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        queue_name: str = "default",
    ) -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name
        self._queue: Any = None
        self._redis: Any = None

    async def startup(self) -> None:
        """Initialise the Redis connection and SAQ queue."""
        try:
            import redis.asyncio as aioredis
            import saq
        except ImportError as exc:
            raise RuntimeError(
                "SAQBackend requires 'saq' and 'redis' packages. "
                "Install with: pip install aura-framework[saq,redis]"
            ) from exc

        self._redis = aioredis.from_url(self._redis_url)
        self._queue = saq.Queue(self._redis, name=self._queue_name)

    async def shutdown(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()

    async def enqueue(
        self,
        task: TaskDefinition,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
        delay: int = 0,
    ) -> TaskResult:
        """Enqueue a task via SAQ.

        Args:
            task: The task definition to execute.
            args: Positional arguments for the task function.
            kwargs: Keyword arguments for the task function.
            delay: Seconds to delay execution.

        Returns:
            A TaskResult with PENDING status.
        """
        if self._queue is None:
            raise RuntimeError("SAQBackend not started. Call startup() first.")

        task_id = str(uuid.uuid4())
        scheduled = int(delay * 1000) if delay > 0 else 0  # SAQ uses milliseconds

        await self._queue.enqueue(
            task.name,
            _task_id=task_id,
            _scheduled=scheduled,
            _timeout=task.timeout * 1000 if task.timeout else None,
            _retries=task.retry,
            args=args,
            **(kwargs or {}),
        )

        return TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
        )

    async def get_result(self, task_id: str) -> TaskResult | None:
        """Retrieve a task result from SAQ/Redis.

        Args:
            task_id: The unique task identifier.

        Returns:
            The TaskResult if found, or None.
        """
        if self._queue is None:
            raise RuntimeError("SAQBackend not started. Call startup() first.")

        try:
            job = await self._queue.job(task_id)
        except Exception:  # noqa: BLE001
            return None

        if job is None:
            return None

        status_map = {
            "queued": TaskStatus.PENDING,
            "active": TaskStatus.RUNNING,
            "complete": TaskStatus.SUCCESS,
            "failed": TaskStatus.FAILED,
            "aborted": TaskStatus.CANCELLED,
        }

        return TaskResult(
            task_id=task_id,
            status=status_map.get(job.status, TaskStatus.PENDING),
            result=job.result,
            error=str(job.error) if job.error else None,
            started_at=(
                datetime.fromtimestamp(job.started / 1000, tz=timezone.utc) if job.started else None
            ),
            completed_at=(
                datetime.fromtimestamp(job.completed / 1000, tz=timezone.utc)
                if job.completed
                else None
            ),
        )

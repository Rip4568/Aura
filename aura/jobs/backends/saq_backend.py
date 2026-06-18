"""SAQ (Simple Async Queue) backend integration for Aura."""

from __future__ import annotations

import functools
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from aura.jobs.backends.base import TaskBackend
from aura.jobs.base import TaskDefinition, TaskResult, TaskStatus

AURA_ARGS_KEY = "__aura_args__"


def wrap_saq_task(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a task so SAQ jobs unpack positional args from ``__aura_args__``."""

    @functools.wraps(func)
    async def wrapper(**kwargs: Any) -> Any:
        aura_args = kwargs.pop(AURA_ARGS_KEY, None)
        if aura_args is not None:
            return await func(*aura_args, **kwargs)
        return await func(**kwargs)

    return wrapper


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

    async def startup(self) -> None:
        """Initialise the SAQ queue from the Redis URL."""
        try:
            from saq import Queue
        except ImportError as exc:
            raise RuntimeError(
                "SAQBackend requires 'saq' and 'redis' packages. "
                "Install with: pip install aura-framework[saq,redis]"
            ) from exc

        self._queue = Queue.from_url(self._redis_url, name=self._queue_name)

    async def shutdown(self) -> None:
        """Disconnect the SAQ queue."""
        if self._queue is not None:
            await self._queue.disconnect()
            self._queue = None

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
        job_kwargs: dict[str, Any] = dict(kwargs or {})
        if args:
            job_kwargs[AURA_ARGS_KEY] = list(args)

        enqueue_opts: dict[str, Any] = {
            "key": task_id,
            "retries": task.retry,
        }
        if task.timeout is not None:
            enqueue_opts["timeout"] = task.timeout
        if delay > 0:
            enqueue_opts["scheduled"] = int(time.time()) + delay

        await self._queue.enqueue(task.name, **job_kwargs, **enqueue_opts)

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
                datetime.fromtimestamp(job.started, tz=timezone.utc)
                if job.started
                else None
            ),
            completed_at=(
                datetime.fromtimestamp(job.completed, tz=timezone.utc)
                if job.completed
                else None
            ),
        )

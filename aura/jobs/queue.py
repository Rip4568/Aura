"""Queue abstraction layer providing a unified interface for task dispatch."""

from __future__ import annotations

from typing import Any

from aura.jobs.backends.base import TaskBackend
from aura.jobs.base import TaskRegistry, TaskResult


class Queue:
    """A named queue that dispatches tasks to a backend.

    Queues provide a higher-level API for sending tasks without holding
    direct references to task functions.

    Args:
        name: Queue name.  Tasks registered on this queue will be processed
              by workers listening to this name.
        backend: The backend to use for enqueuing.

    Example::

        queue = Queue("emails", backend=redis_backend)
        result = await queue.send("myapp.tasks.send_email", user_id=1)
    """

    def __init__(self, name: str, backend: TaskBackend) -> None:
        self.name = name
        self._backend = backend

    async def send(self, task_name: str, *args: Any, **kwargs: Any) -> TaskResult:
        """Dispatch a task to this queue by its registered name.

        Args:
            task_name: The fully-qualified name of the registered task.
            *args: Positional arguments forwarded to the task.
            **kwargs: Keyword arguments forwarded to the task.

        Returns:
            A :class:`~aura.jobs.base.TaskResult` with PENDING status.

        Raises:
            ValueError: If *task_name* is not registered in the
                        :class:`~aura.jobs.base.TaskRegistry`.
        """
        task_def = TaskRegistry.get(task_name)
        if task_def is None:
            raise ValueError(f"No task registered with name {task_name!r}")

        return await self._backend.enqueue(
            task=task_def,
            args=args,
            kwargs=kwargs,
        )

    async def send_at(
        self,
        task_name: str,
        delay: int,
        *args: Any,
        **kwargs: Any,
    ) -> TaskResult:
        """Dispatch a task after *delay* seconds.

        Args:
            task_name: The fully-qualified name of the registered task.
            delay: Seconds to wait before executing.
            *args: Positional arguments forwarded to the task.
            **kwargs: Keyword arguments forwarded to the task.

        Returns:
            A :class:`~aura.jobs.base.TaskResult` with PENDING status.
        """
        task_def = TaskRegistry.get(task_name)
        if task_def is None:
            raise ValueError(f"No task registered with name {task_name!r}")

        return await self._backend.enqueue(
            task=task_def,
            args=args,
            kwargs=kwargs,
            delay=delay,
        )

    def __repr__(self) -> str:
        return f"<Queue name={self.name!r} backend={type(self._backend).__name__!r}>"

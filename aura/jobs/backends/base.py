"""Abstract interface for Aura task queue backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from aura.jobs.base import TaskDefinition, TaskResult


class TaskBackend(ABC):
    """Abstract base class for task queue backend implementations.

    All concrete backends (memory, SAQ, Redis, etc.) must implement
    this interface so that task dispatch code stays backend-agnostic.
    """

    @abstractmethod
    async def startup(self) -> None:
        """Initialise the backend (open connections, create queues, …)."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shut down the backend and release resources."""
        ...

    @abstractmethod
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
            A TaskResult with the generated task_id and initial status.
        """
        ...

    @abstractmethod
    async def get_result(self, task_id: str) -> TaskResult | None:
        """Retrieve the result of a previously dispatched task.

        Args:
            task_id: The unique identifier returned when the task was enqueued.

        Returns:
            The TaskResult if found, or None.
        """
        ...

"""Base classes and abstractions for the Aura jobs/tasks system."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar
import uuid

if TYPE_CHECKING:
    from aura.jobs.backends.base import TaskBackend

F = TypeVar("F", bound=Callable[..., Any])


class TaskStatus(str, Enum):
    """Possible states for a task execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of a dispatched task execution."""

    task_id: str
    status: TaskStatus
    result: Any = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class TaskDefinition:
    """Metadata and configuration for a registered task."""

    func: Callable[..., Any]
    name: str
    queue: str = "default"
    retry: int = 0
    timeout: int | None = None
    priority: int = 0
    description: str = ""


class AuraTask:
    """
    Represents a registered task in Aura.

    Wraps a coroutine function with dispatch/scheduling capabilities.

    Usage::

        @task(queue="emails", retry=3, timeout=30)
        async def send_welcome_email(user_id: int, email: str):
            ...

        # Dispatch asynchronously:
        await send_welcome_email.dispatch(user_id=1, email="user@example.com")

        # Dispatch with delay (seconds):
        await send_welcome_email.dispatch_at(delay=60, user_id=1, email="...")

        # Run synchronously (testing):
        result = await send_welcome_email.run_sync(user_id=1, email="...")
    """

    def __init__(self, definition: TaskDefinition, backend: "TaskBackend") -> None:
        self.definition = definition
        self._backend = backend
        # Preserve wrapped function attributes
        self.__name__ = definition.func.__name__
        self.__qualname__ = definition.func.__qualname__
        self.__module__ = definition.func.__module__
        self.__doc__ = definition.func.__doc__

    async def dispatch(self, *args: Any, **kwargs: Any) -> TaskResult:
        """Enqueue the task for asynchronous execution.

        Args:
            *args: Positional arguments forwarded to the task function.
            **kwargs: Keyword arguments forwarded to the task function.

        Returns:
            TaskResult with initial PENDING status and a task_id.
        """
        return await self._backend.enqueue(
            task=self.definition,
            args=args,
            kwargs=kwargs,
        )

    async def dispatch_at(self, delay: int, *args: Any, **kwargs: Any) -> TaskResult:
        """Enqueue the task to run after *delay* seconds.

        Args:
            delay: Seconds to wait before executing the task.
            *args: Positional arguments forwarded to the task function.
            **kwargs: Keyword arguments forwarded to the task function.

        Returns:
            TaskResult with initial PENDING status and a task_id.
        """
        return await self._backend.enqueue(
            task=self.definition,
            args=args,
            kwargs=kwargs,
            delay=delay,
        )

    async def run_sync(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the task inline (no queue), useful for testing.

        Args:
            *args: Positional arguments forwarded to the task function.
            **kwargs: Keyword arguments forwarded to the task function.

        Returns:
            The raw return value of the task function.
        """
        return await self.definition.func(*args, **kwargs)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow direct call — returns the coroutine for direct awaiting."""
        return self.definition.func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"<AuraTask name={self.definition.name!r} queue={self.definition.queue!r}>"


class TaskRegistry:
    """Global registry of all tasks registered via decorators."""

    _tasks: dict[str, TaskDefinition] = {}

    @classmethod
    def register(cls, task_def: TaskDefinition) -> None:
        """Register a task definition by name.

        Args:
            task_def: The TaskDefinition to register.
        """
        cls._tasks[task_def.name] = task_def

    @classmethod
    def get(cls, name: str) -> TaskDefinition | None:
        """Look up a task definition by its qualified name.

        Args:
            name: The task's registered name.

        Returns:
            The TaskDefinition, or None if not found.
        """
        return cls._tasks.get(name)

    @classmethod
    def all(cls) -> dict[str, TaskDefinition]:
        """Return a copy of all registered task definitions."""
        return dict(cls._tasks)

    @classmethod
    def clear(cls) -> None:
        """Remove all registered tasks (used in tests)."""
        cls._tasks.clear()

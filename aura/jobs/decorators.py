"""Decorators for registering Aura tasks and periodic jobs."""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from aura.jobs.base import AuraTask, TaskDefinition, TaskRegistry

F = TypeVar("F", bound=Callable[..., Any])

# Global default backend (lazily initialised on first use)
_default_backend: Any = None


def _get_default_backend() -> Any:
    """Instantiate the correct backend based on environment configuration.

    If the ``AURA__JOBS__BROKER_URL`` environment variable is set, a
    :class:`~aura.jobs.backends.saq_backend.SAQBackend` is returned.
    Otherwise the in-process :class:`~aura.jobs.backends.memory.MemoryBackend`
    is used.

    SAQ/redis packages are imported lazily to avoid hard dependencies.
    """
    broker_url = os.environ.get("AURA__JOBS__BROKER_URL")
    if broker_url:
        from aura.jobs.backends.saq_backend import SAQBackend

        return SAQBackend(redis_url=broker_url)
    from aura.jobs.backends.memory import MemoryBackend

    return MemoryBackend()


def _get_backend() -> Any:
    """Return the global backend, initialising it on first call if needed."""
    global _default_backend
    if _default_backend is None:
        _default_backend = _get_default_backend()
    return _default_backend


def set_backend(backend: Any) -> None:
    """Replace the global default backend.

    Called by the Aura app during startup when a backend is configured.

    Args:
        backend: A TaskBackend instance to use as the default.
    """
    global _default_backend
    _default_backend = backend


def task(
    *,
    queue: str = "default",
    retry: int = 0,
    timeout: int | None = None,
    priority: int = 0,
    name: str | None = None,
) -> Callable[[F], AuraTask]:
    """Register a coroutine function as an Aura background task.

    Args:
        queue: Name of the queue to dispatch tasks to.
        retry: Number of retry attempts on failure (0 = no retries).
        timeout: Execution timeout in seconds (None = unlimited).
        priority: Task priority; higher numbers are processed first.
        name: Override the default qualified-name task identifier.

    Returns:
        A decorator that wraps the function as an :class:`AuraTask`.

    Example::

        @task(queue="emails", retry=3, timeout=30)
        async def send_welcome_email(user_id: int, email: str) -> None:
            await email_service.send(email, template="welcome")

        # Dispatch:
        await send_welcome_email.dispatch(user_id=1, email="user@example.com")
    """

    def decorator(func: F) -> AuraTask:
        task_name = name or f"{func.__module__}.{func.__qualname__}"
        definition = TaskDefinition(
            func=func,
            name=task_name,
            queue=queue,
            retry=retry,
            timeout=timeout,
            priority=priority,
            description=func.__doc__ or "",
        )
        TaskRegistry.register(definition)

        aura_task = AuraTask(
            definition=definition,
            backend=_get_backend(),
        )
        functools.update_wrapper(aura_task, func)
        return aura_task

    return decorator


@dataclass
class PeriodicTaskDefinition(TaskDefinition):
    """Extended TaskDefinition carrying cron scheduling metadata."""

    cron: str = ""
    run_on_startup: bool = False


def periodic(
    cron: str,
    *,
    queue: str = "default",
    timeout: int | None = None,
    name: str | None = None,
    run_on_startup: bool = False,
) -> Callable[[F], AuraTask]:
    """Register a coroutine function as a periodic/scheduled Aura task.

    Args:
        cron: Cron expression defining the schedule (e.g. ``"0 8 * * *"``
              for daily at 08:00).
        queue: Name of the queue to dispatch tasks to.
        timeout: Execution timeout in seconds (None = unlimited).
        name: Override the default qualified-name task identifier.
        run_on_startup: If ``True``, the task is executed immediately on
                        worker startup in addition to its cron schedule.

    Returns:
        A decorator that wraps the function as an :class:`AuraTask`.

    Example::

        @periodic(cron="0 8 * * *", run_on_startup=True)
        async def daily_digest() -> None:
            await report_service.send_daily_report()
    """

    def decorator(func: F) -> AuraTask:
        task_name = name or f"{func.__module__}.{func.__qualname__}"
        definition = PeriodicTaskDefinition(
            func=func,
            name=task_name,
            queue=queue,
            timeout=timeout,
            cron=cron,
            run_on_startup=run_on_startup,
        )
        TaskRegistry.register(definition)

        aura_task = AuraTask(
            definition=definition,
            backend=_get_backend(),
        )
        functools.update_wrapper(aura_task, func)
        return aura_task

    return decorator

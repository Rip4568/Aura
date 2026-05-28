"""DI provider types for the Aura framework."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


class Provider(ABC, Generic[T]):
    """
    Abstract base class for all DI providers.

    A provider knows how to create (or retrieve) an instance of a
    specific type.  Concrete subclasses implement different *lifetimes*:
    singleton, transient, and scoped.
    """

    @abstractmethod
    async def get(self, container: Any) -> T:
        """
        Resolve and return the managed instance.

        Args:
            container: The :class:`~aura.di.container.DIContainer` that
                owns this provider (used for recursive dependency resolution).

        Returns:
            The resolved instance.
        """
        ...


class SingletonProvider(Provider[T]):
    """
    Provider that creates a single shared instance for the application lifetime.

    The instance is created on the first call to :meth:`get` and reused
    thereafter.  The creation is protected by an :class:`asyncio.Lock` so it
    is safe to call :meth:`get` concurrently.

    Args:
        factory: An async (or sync) callable that produces the instance.
    """

    def __init__(self, factory: Callable[..., Any]) -> None:
        self._factory = factory
        self._instance: T | None = None
        self._lock = asyncio.Lock()

    async def get(self, container: Any) -> T:
        """Return the singleton, creating it if this is the first call."""
        if self._instance is None:
            async with self._lock:
                # Double-checked locking
                if self._instance is None:
                    self._instance = cast(T, await _call(self._factory, container))
        return self._instance


class TransientProvider(Provider[T]):
    """
    Provider that creates a new instance on every call to :meth:`get`.

    Args:
        factory: An async (or sync) callable that produces the instance.
    """

    def __init__(self, factory: Callable[..., Any]) -> None:
        self._factory = factory

    async def get(self, container: Any) -> T:
        """Create and return a brand-new instance."""
        return cast(T, await _call(self._factory, container))


class ScopedProvider(Provider[T]):
    """
    Provider that creates one instance per *scope*.

    A scope is typically a single HTTP request.  Scoped providers behave
    like singletons within a scope but create a fresh instance for each
    new scope.

    Args:
        factory: An async (or sync) callable that produces the instance.
    """

    def __init__(self, factory: Callable[..., Any]) -> None:
        self._factory = factory
        self._scope_instances: dict[int, T] = {}
        self._lock = asyncio.Lock()

    async def get(self, container: Any) -> T:
        """Return the scoped instance, creating it within the current scope if absent."""
        scope_id = id(container)
        if scope_id not in self._scope_instances:
            async with self._lock:
                if scope_id not in self._scope_instances:
                    self._scope_instances[scope_id] = await _call(self._factory, container)
        return self._scope_instances[scope_id]

    def clear_scope(self, container: Any) -> None:
        """Remove the cached instance for the given scope.

        Args:
            container: The container whose scope should be cleared.
        """
        self._scope_instances.pop(id(container), None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _call(factory: Callable[..., Any], container: Any) -> Any:
    """Invoke *factory* with zero arguments, awaiting it if it is a coroutine.

    Args:
        factory: Callable to invoke.
        container: The container (not currently forwarded to bare factories).

    Returns:
        The result of calling *factory*.
    """
    result = factory()
    if asyncio.iscoroutine(result):
        return await result
    return result

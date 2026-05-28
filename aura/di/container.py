"""Dependency Injection container for the Aura framework."""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar, cast, get_type_hints, overload  # noqa: F401

from aura.di.providers import (
    Provider,
    ScopedProvider,
    SingletonProvider,
    TransientProvider,
)

logger = logging.getLogger("aura.di")

T = TypeVar("T")


class Lifetime(str, Enum):
    """Defines how long a resolved dependency instance lives.

    Attributes:
        SINGLETON: One instance shared across the entire application.
        SCOPED: One instance per request (or per explicit scope).
        TRANSIENT: A new instance every time the dependency is resolved.
    """

    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


class DIContainer:
    """
    Async-aware Dependency Injection container.

    Supports three lifetimes (:attr:`Lifetime.SINGLETON`,
    :attr:`Lifetime.SCOPED`, :attr:`Lifetime.TRANSIENT`) and resolves
    constructor dependencies automatically via type hints.

    Usage::

        container = DIContainer()
        container.register(UserRepository, lifetime=Lifetime.SINGLETON)
        container.register(UserService, lifetime=Lifetime.SCOPED)

        # Later, inside a request handler:
        service = await container.resolve(UserService)

    Factories can also be provided explicitly::

        container.register_factory(
            EmailService,
            factory=lambda: EmailService(smtp_host="localhost"),
            lifetime=Lifetime.SINGLETON,
        )
    """

    def __init__(self) -> None:
        self._providers: dict[type, Provider[Any]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        service_type: type[T],
        *,
        implementation: type[T] | None = None,
        lifetime: Lifetime = Lifetime.SINGLETON,
    ) -> None:
        """Register a class as a dependency.

        Args:
            service_type: The abstract type (or concrete class) used as the
                registration key and for dependency lookup.
            implementation: The concrete class to instantiate.  Defaults to
                *service_type* when not provided.
            lifetime: How long the created instance should live.
        """
        impl = implementation or service_type
        factory = self._make_factory(impl)
        self._set_provider(service_type, factory, lifetime)
        logger.debug("Registered %s as %s (%s)", impl.__name__, service_type.__name__, lifetime)

    def register_factory(
        self,
        service_type: type[T],
        *,
        factory: Callable[[], T],
        lifetime: Lifetime = Lifetime.SINGLETON,
    ) -> None:
        """Register an explicit factory callable.

        Args:
            service_type: The type used as the registration key.
            factory: A zero-argument callable (sync or async) that returns an
                instance of *service_type*.
            lifetime: How long the created instance should live.
        """
        self._set_provider(service_type, factory, lifetime)
        logger.debug(
            "Registered factory for %s (%s)", service_type.__name__, lifetime
        )

    def register_instance(self, service_type: type[T], instance: T) -> None:
        """Register a pre-built instance as a singleton.

        Args:
            service_type: The type used as the registration key.
            instance: The already-created instance to return on every resolve.
        """
        async def _factory() -> T:
            return instance

        self._providers[service_type] = SingletonProvider(_factory)
        logger.debug("Registered instance for %s", service_type.__name__)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    async def resolve(self, service_type: type[T]) -> T:
        """Resolve a registered dependency by type.

        Args:
            service_type: The type to resolve.

        Returns:
            The resolved instance.

        Raises:
            KeyError: If *service_type* is not registered.
        """
        provider = self._providers.get(service_type)
        if provider is None:
            raise KeyError(
                f"No provider registered for '{service_type.__name__}'. "
                "Did you forget to add it to the module's providers list?"
            )
        return cast(T, await provider.get(self))

    async def resolve_optional(self, service_type: type[T]) -> T | None:
        """Like :meth:`resolve` but returns ``None`` when *service_type* is not registered.

        Args:
            service_type: The type to resolve.

        Returns:
            The resolved instance, or ``None`` if not registered.
        """
        try:
            return await self.resolve(service_type)
        except KeyError:
            return None

    def is_registered(self, service_type: type) -> bool:
        """Return ``True`` if *service_type* has a provider registered.

        Args:
            service_type: The type to check.
        """
        return service_type in self._providers

    # ------------------------------------------------------------------
    # Scoped sub-container
    # ------------------------------------------------------------------

    def create_scope(self) -> DIContainer:
        """Create a child container that shares singleton registrations but
        maintains its own scoped instances.

        Returns:
            A new :class:`DIContainer` sharing the parent's providers.
        """
        child = DIContainer()
        child._providers = dict(self._providers)
        return child

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Eagerly resolve all singleton providers so they are warmed up.

        This is called by :class:`~aura.core.app.Aura` during application
        startup.
        """
        for service_type, provider in self._providers.items():
            if isinstance(provider, SingletonProvider):
                try:
                    await provider.get(self)
                    logger.debug("Warmed up singleton: %s", service_type.__name__)
                except Exception:
                    logger.exception("Failed to warm up singleton: %s", service_type.__name__)

    async def shutdown(self) -> None:
        """Release resources held by providers (no-op for now).

        Subclasses or future versions may add cleanup logic here.
        """
        logger.debug("DIContainer shutdown complete")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_provider(
        self,
        service_type: type,
        factory: Callable[[], Any],
        lifetime: Lifetime,
    ) -> None:
        provider: Provider[Any]
        if lifetime == Lifetime.SINGLETON:
            provider = SingletonProvider(factory)
        elif lifetime == Lifetime.SCOPED:
            provider = ScopedProvider(factory)
        else:
            provider = TransientProvider(factory)
        self._providers[service_type] = provider

    def _make_factory(self, impl: type) -> Callable[[], Any]:
        """Build an async factory that auto-resolves constructor dependencies.

        Args:
            impl: The concrete class to instantiate.

        Returns:
            An async zero-argument callable that resolves all constructor
            dependencies and returns a new *impl* instance.
        """
        container_ref = self

        async def factory() -> Any:
            kwargs: dict[str, Any] = {}
            hints = _get_init_type_hints(impl)
            for param_name, param_type in hints.items():
                if param_name == "return":
                    continue
                dep = await container_ref.resolve_optional(param_type)
                if dep is not None:
                    kwargs[param_name] = dep
            return impl(**kwargs)

        return factory


def _get_init_type_hints(cls: type) -> dict[str, Any]:
    """Return type hints for ``__init__`` parameters, excluding ``self``.

    Args:
        cls: The class to inspect.

    Returns:
        Mapping of parameter name → annotated type.
    """
    try:
        hints = {}
        sig = inspect.signature(cls)
        type_hints: dict[str, Any] = {}
        try:
            type_hints = get_type_hints(cls.__init__, include_extras=True)  # type: ignore[misc]
        except Exception:
            pass
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if name in type_hints:
                hints[name] = type_hints[name]
            elif param.annotation is not inspect.Parameter.empty:
                hints[name] = param.annotation
        return hints
    except (TypeError, ValueError):
        return {}

"""Dependency Injection container for the Aura framework."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import logging
from collections.abc import Callable
from enum import Enum
from typing import Any, TypeVar, Union, cast, get_type_hints, overload  # noqa: F401

from aura.di.providers import (
    Provider,
    ScopedProvider,
    SingletonProvider,
    TransientProvider,
)

logger = logging.getLogger("aura.di")

T = TypeVar("T")

# Context variable to track which types are currently being resolved (for cycle detection)
_resolving_types: contextvars.ContextVar[frozenset[type]] = contextvars.ContextVar(
    "_resolving_types", default=frozenset()
)


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
        self._scoped_cache: dict[type, Any] = {}

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
        factory = self._make_factory(impl, lifetime=lifetime)
        self._set_provider(service_type, factory, lifetime)
        logger.debug(
            "Registered %s as %s (%s)", _type_name(impl), _type_name(service_type), lifetime
        )

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
            "Registered factory for %s (%s)", _type_name(service_type), lifetime
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
        logger.debug("Registered instance for %s", _type_name(service_type))

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
            RuntimeError: If a circular dependency is detected.
        """
        # Check for circular dependency
        resolving = _resolving_types.get()
        if service_type in resolving:
            raise RuntimeError(
                f"DIContainer: Circular dependency detected for '{_type_name(service_type)}'"
            )

        provider = self._providers.get(service_type)
        if provider is None:
            raise KeyError(
                f"No provider registered for '{_type_name(service_type)}'. "
                "Did you forget to add it to the module's providers list?"
            )

        # Add to resolving set and resolve
        resolving_updated = resolving | frozenset([service_type])
        token = _resolving_types.set(resolving_updated)
        try:
            return cast(T, await provider.get(self))
        finally:
            _resolving_types.reset(token)

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

    def clear_scope_cache(self) -> None:
        """Clear scoped instances for the current request scope."""
        self._scoped_cache.clear()

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
                    logger.debug("Warmed up singleton: %s", _type_name(service_type))
                except Exception:
                    logger.exception("Failed to warm up singleton: %s", _type_name(service_type))

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
            provider = ScopedProvider(factory, service_type)
        else:
            provider = TransientProvider(factory)
        self._providers[service_type] = provider

    def _make_factory(
        self, impl: type, lifetime: Lifetime = Lifetime.SINGLETON
    ) -> Callable[..., Any]:
        """Build an async factory that auto-resolves constructor dependencies.

        Args:
            impl: The concrete class to instantiate.
            lifetime: The Lifetime of the registered service.

        Returns:
            An async callable that resolves all constructor
            dependencies and returns a new *impl* instance.
        """
        container_ref = self

        async def factory(container: DIContainer | None = None) -> Any:
            kwargs: dict[str, Any] = {}
            hints = _get_init_type_hints(impl)
            sig = inspect.signature(impl)

            # Retrieve active container resolving context
            active_c = container or container_ref

            for param_name, param_type in hints.items():
                if param_name == "return":
                    continue

                param_type, _inject_marker = _parse_dependency_type(param_type)

                # Determine if this parameter is optional
                is_optional = _is_optional_type(param_type)
                param_obj = sig.parameters.get(param_name)
                has_default = param_obj and param_obj.default is not inspect.Parameter.empty

                # Captive dependency check:
                # If impl is SINGLETON but the parameter is registered as SCOPED, raise error
                dep_provider = container_ref._providers.get(param_type)
                if dep_provider is not None and lifetime == Lifetime.SINGLETON:
                    from aura.di.providers import ScopedProvider
                    if isinstance(dep_provider, ScopedProvider):
                        raise RuntimeError(
                            f"DIContainer: Captive dependency detected! "
                            f"Singleton '{_type_name(impl)}' depends on "
                            f"Scoped service '{_type_name(param_type)}'. "
                            f"This will cause the request-scoped instance "
                            f"to be captured by the singleton, causing "
                            f"database transaction leakage. Please decorate "
                            f"'{_type_name(impl)}' with "
                            f"@injectable(lifetime=Lifetime.SCOPED)."
                        )

                # Try to resolve the dependency
                dep = await active_c.resolve_optional(param_type)

                if dep is not None:
                    kwargs[param_name] = dep
                elif not is_optional and not has_default:
                    # Required dependency not registered and no default
                    raise RuntimeError(
                        f"DIContainer: '{_type_name(impl)}' depends on "
                        f"'{_type_name(param_type)}' which is not registered. "
                        f"Add it to the module's providers list."
                    )

            return impl(**kwargs)

        return factory


def _parse_dependency_type(type_hint: Any) -> tuple[Any, Any | None]:
    """Unwrap ``Annotated[T, inject()]`` into the inner type and optional marker."""
    from typing import Annotated, get_args, get_origin

    from aura.di.decorators import InjectMarker

    if get_origin(type_hint) is Annotated:
        args = get_args(type_hint)
        if not args:
            return type_hint, None
        inner_type = args[0]
        marker: Any | None = None
        for meta in args[1:]:
            if isinstance(meta, InjectMarker):
                marker = meta
        return inner_type, marker
    return type_hint, None


def _is_optional_type(type_hint: Any) -> bool:
    """Check if a type hint represents an optional type.

    A type is optional if it is Union[X, None], Optional[X], or X | None.

    Args:
        type_hint: The type hint to check.

    Returns:
        True if the type is optional, False otherwise.
    """
    # Check new Python 3.10+ UnionType (e.g. Logger | None)
    try:
        import types
        if hasattr(types, "UnionType") and isinstance(type_hint, types.UnionType):
            args = getattr(type_hint, "__args__", ())
            return type(None) in args
    except AttributeError:
        pass

    # Get the origin (Union, Optional, etc.)
    origin = getattr(type_hint, "__origin__", None)

    # Check if it's Union and has None in args
    if origin is Union:
        args = getattr(type_hint, "__args__", ())
        return type(None) in args
    return False


def _type_name(type_hint: Any) -> str:
    """Get a readable name for a type hint.

    Args:
        type_hint: The type hint to get a name for.

    Returns:
        A readable string representation of the type.
    """
    if hasattr(type_hint, "__name__"):
        return cast(str, type_hint.__name__)
    return str(type_hint)


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


# Global container instance
container = DIContainer()


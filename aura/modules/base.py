"""Module decorator and metadata for the Aura framework."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any


class ModuleMetadata:
    """
    Container for metadata attached to an Aura module class.

    An Aura module is a class decorated with :func:`Module` that groups
    together related *controllers*, *providers*, *imports* and *exports*.
    This follows the NestJS module pattern adapted for Python.

    Attributes:
        imports: Other module classes whose exported providers become available
            inside this module.
        providers: Injectable classes (services, repositories, etc.) managed
            by the DI container within this module's scope.
        controllers: Classes or instances that define route handlers.
        exports: Providers to re-export so that importing modules can access
            them.
        prefix: URL prefix applied to all controllers in this module.
        tags: Default OpenAPI tags for all routes in this module.
        guards: Guards evaluated for every route in this module.
    """

    def __init__(
        self,
        imports: Sequence[type] = (),
        providers: Sequence[type] = (),
        controllers: Sequence[Any] = (),
        exports: Sequence[type] = (),
        prefix: str = "",
        tags: list[str] | None = None,
        guards: list[Any] | None = None,
    ) -> None:
        self.imports = list(imports)
        self.providers = list(providers)
        self.controllers = list(controllers)
        self.exports = list(exports)
        self.prefix = prefix
        self.tags = tags or []
        self.guards = guards or []


def Module(  # noqa: N802
    *,
    imports: Sequence[type] = (),
    providers: Sequence[type] = (),
    controllers: Sequence[Any] = (),
    exports: Sequence[type] = (),
    prefix: str = "",
    tags: list[str] | None = None,
    guards: list[Any] | None = None,
) -> Callable[[type], type]:
    """
    Class decorator that defines an Aura module.

    A *module* is the primary organisational unit in an Aura application.
    It groups controllers (route handlers), providers (services), and
    can import from or export to other modules.

    Args:
        imports: Modules whose exported providers are available here.
        providers: Injectable classes scoped to this module.
        controllers: Classes with route handler methods.
        exports: Subset of *providers* to expose to importing modules.
        prefix: URL prefix prepended to all routes in this module.
        tags: Default OpenAPI tags for all routes in this module.
        guards: Guards evaluated before every route in this module.

    Returns:
        The original class with ``__aura_module__`` metadata attached.

    Example::

        @Module(
            controllers=[UserController],
            providers=[UserService, UserRepository],
            exports=[UserService],
            prefix="/users",
        )
        class UserModule:
            pass
    """

    def decorator(cls: type) -> type:
        cls.__aura_module__ = ModuleMetadata(  # type: ignore[attr-defined]
            imports=imports,
            providers=providers,
            controllers=controllers,
            exports=exports,
            prefix=prefix,
            tags=tags,
            guards=guards,
        )
        return cls

    return decorator

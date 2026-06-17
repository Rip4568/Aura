"""Module registry for collecting routes and providers from all modules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from starlette.routing import Route, WebSocketRoute

if TYPE_CHECKING:
    from aura.di.container import DIContainer

logger = logging.getLogger("aura.modules")


class ModuleRegistry:
    """
    Registry that traverses the module tree, registers providers into the DI
    container, and collects all route handlers.

    The registry respects module ``imports`` so that exported providers from
    one module are available in modules that import it.

    Args:
        container: The application-level :class:`~aura.di.container.DIContainer`.
    """

    def __init__(self, container: DIContainer) -> None:
        self.container = container
        self._modules: list[type] = []
        self._registered: set[type] = set()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, module_class: type) -> None:
        """Register a module class and all its transitive imports.

        Args:
            module_class: A class decorated with :func:`~aura.modules.base.Module`.

        Raises:
            TypeError: If *module_class* does not have ``__aura_module__``
                metadata (i.e. was not decorated with ``@Module``).
        """
        if not hasattr(module_class, "__aura_module__"):
            raise TypeError(
                f"{module_class.__name__!r} is not an Aura module. "
                "Did you forget the @Module decorator?"
            )
        self._register_module(module_class)

    def _register_module(self, module_class: type) -> None:
        """Recursively register a module and its imports.

        Args:
            module_class: Module class to register.
        """
        if module_class in self._registered:
            return
        self._registered.add(module_class)

        meta = module_class.__aura_module__  # type: ignore[attr-defined]

        # Register imported modules first
        for imported in meta.imports:
            self._register_module(imported)

        # Register providers into the DI container
        for provider_class in meta.providers:
            self._register_provider(provider_class)

        # Register controllers into the DI container so they can be resolved with dependencies
        from aura.di.container import Lifetime
        for controller_class in meta.controllers:
            if not self.container.is_registered(controller_class):
                self.container.register(controller_class, lifetime=Lifetime.SCOPED)

        self._modules.append(module_class)
        logger.debug("Module registered: %s", module_class.__name__)

    def _register_provider(self, provider_class: type) -> None:
        """Register a single provider class into the DI container.

        Respects the ``__aura_injectable__`` metadata set by
        :func:`~aura.di.decorators.injectable` when determining lifetime.

        Args:
            provider_class: The service/repository class to register.
        """

        meta = getattr(provider_class, "__aura_injectable__", None)
        if not meta:
            raise TypeError(
                f"Provider {provider_class.__name__!r} is not decorated with @injectable. "
                "All providers registered in a Module must be decorated with @injectable."
            )
        lifetime = meta["lifetime"]

        self.container.register(provider_class, lifetime=lifetime)
        logger.debug(
            "Provider registered: %s (%s)", provider_class.__name__, lifetime
        )

    # ------------------------------------------------------------------
    # Module lifecycle
    # ------------------------------------------------------------------

    async def run_module_startups(self, container: Any, debug: bool = False) -> None:
        """Call ``on_startup(container, debug)`` on every module that defines it.

        Modules may define either a regular or an ``async`` classmethod /
        staticmethod named ``on_startup``.  Both are supported.

        Args:
            container: The application DI container.
            debug: Whether the application is running in debug mode.
        """
        import asyncio
        import inspect

        for module_class in self._modules:
            startup_fn = getattr(module_class, "on_startup", None)
            if startup_fn is None:
                continue
            try:
                result = startup_fn(container, debug)
                if asyncio.iscoroutine(result) or inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception(
                    "Error in on_startup for module %s", module_class.__name__
                )

    # ------------------------------------------------------------------
    # Route collection
    # ------------------------------------------------------------------

    def collect_routes(
        self,
        openapi_gen: Any | None = None,
        global_guards: list[Any] | None = None,
        global_prefix: str = "",
    ) -> list[Route | WebSocketRoute]:
        """Collect all routes from all registered modules.

        Args:
            openapi_gen: Optional OpenAPI generator to register route metadata
                with.
            global_guards: Application-level guards to prepend.
            global_prefix: URL prefix from :class:`~aura.core.app.Aura` applied
                to every module route.

        Returns:
            Flat list of Starlette route objects.
        """
        from aura.routing.router import Router

        all_routes: list[Route | WebSocketRoute] = []
        app_prefix = global_prefix.rstrip("/")

        for module_class in self._modules:
            meta = module_class.__aura_module__  # type: ignore[attr-defined]
            module_prefix = meta.prefix.rstrip("/")
            if app_prefix and module_prefix:
                combined_prefix = f"{app_prefix}/{module_prefix.lstrip('/')}"
            else:
                combined_prefix = app_prefix or module_prefix
            module_guards = list(global_guards or []) + list(meta.guards)

            router = Router(prefix=combined_prefix, tags=meta.tags)

            for controller in meta.controllers:
                router.include_controller(controller, prefix="")

            module_routes = router.build_routes(
                openapi_gen=openapi_gen,
                global_guards=module_guards,
            )
            all_routes.extend(module_routes)

        return all_routes

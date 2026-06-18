"""Main Aura application class."""

from __future__ import annotations

import contextlib
import logging
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any, cast

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from aura.config.base import AuraConfig
from aura.di.container import DIContainer
from aura.exceptions.handlers import exception_handler
from aura.modules.registry import ModuleRegistry
from aura.routing.router import Router
from aura.schema.openapi import OpenAPIGenerator

logger = logging.getLogger("aura")

_SENSITIVE_CONFIG_KEYS = frozenset(
    {"secret_key", "password", "token", "url", "broker_url", "dsn"}
)


def _redact_sensitive_values(data: Any) -> Any:
    """Recursively redact sensitive configuration values for logging."""
    if isinstance(data, dict):
        redacted: dict[str, Any] = {}
        for key, value in data.items():
            if key.lower() in _SENSITIVE_CONFIG_KEYS:
                redacted[key] = "***"
            else:
                redacted[key] = _redact_sensitive_values(value)
        return redacted
    if isinstance(data, list):
        return [_redact_sensitive_values(item) for item in data]
    return data


def _safe_config_dump(cfg: AuraConfig) -> dict[str, Any]:
    """Return a log-safe representation of application config."""
    result = _redact_sensitive_values(cfg.model_dump())
    assert isinstance(result, dict)
    return result


def _load_dotenv(env_path: str = ".env") -> None:
    """Load variables from a .env file into os.environ if present, without overwriting."""
    if os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key and key not in os.environ:
                            os.environ[key] = val
        except Exception:
            pass


class Aura:
    """
    Main Aura application class.

    Composes all framework subsystems into a single ASGI application:
    modules, DI container, routing, OpenAPI generation, and lifecycle hooks.

    Args:
        modules: Top-level module classes to register.
        middleware: Global ASGI middleware applied to every request.
        guards: Global guards evaluated before every route handler.
        config: A :class:`~aura.config.base.AuraConfig` subclass to
            instantiate and bind as a singleton in the container.
        title: Application title shown in the OpenAPI spec and docs UI.
        version: Application version string.
        description: Markdown description shown in the docs UI.
        debug: Enable debug mode (verbose error responses).
        prefix: Global URL prefix for all routes.
        docs_url: Path to the Swagger UI page.  ``None`` disables it.
        openapi_url: Path to the raw OpenAPI JSON endpoint.  ``None`` disables it.
        redoc_url: Path to the Redoc UI page.  ``None`` disables it.

    Example::

        app = Aura(
            modules=[UserModule, AuthModule],
            title="My API",
            version="1.0.0",
        )
    """

    def __init__(
        self,
        *,
        modules: Sequence[type] = (),
        middleware: Sequence[Any] = (),
        guards: Sequence[Any] = (),
        interceptors: Sequence[Any] = (),
        config: type[AuraConfig] | None = None,
        title: str = "Aura App",
        version: str = "0.1.0",
        description: str = "",
        debug: bool = False,
        prefix: str = "",
        docs_url: str | None = "/docs",
        openapi_url: str | None = "/openapi.json",
        redoc_url: str | None = "/redoc",
    ) -> None:
        _load_dotenv()
        self.title = title
        self.version = version
        self.description = description
        self.debug = debug
        self.prefix = prefix.rstrip("/")
        self.docs_url = docs_url
        self.openapi_url = openapi_url
        self.redoc_url = redoc_url

        # Core subsystems
        self.container = DIContainer()
        self.registry = ModuleRegistry(self.container)
        self.router = Router(prefix=self.prefix)
        self.openapi = OpenAPIGenerator(
            title=title,
            version=version,
            description=description,
        )

        # Config
        self._config_class = config or AuraConfig

        # Middleware, guards, and interceptors
        self._global_middleware = list(middleware)
        self._global_guards = list(guards)
        self._interceptors = list(interceptors)

        # Register all modules
        for module in modules:
            self.registry.register(module)

        # The built ASGI app — populated lazily on first request
        self._app: ASGIApp | None = None

    # ------------------------------------------------------------------
    # ASGI interface
    # ------------------------------------------------------------------

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI entry point.

        Lazily builds the application on the first call so that all module
        registrations happen before the first request is processed.
        """
        if self._app is None:
            self._app = self._build()
        await self._app(scope, receive, send)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> ASGIApp:
        """Assemble all routes, middleware, and exception handlers into a
        Starlette ASGI application.

        Returns:
            The fully configured Starlette application.
        """
        # Collect module routes (also registers them in openapi)
        routes = self.registry.collect_routes(
            openapi_gen=self.openapi,
            global_guards=self._global_guards,
            global_prefix=self.prefix,
            global_interceptors=self._interceptors,
        )

        # Meta routes: OpenAPI, docs
        if self.openapi_url:
            routes.append(self._openapi_route())
        if self.docs_url:
            routes.append(self._swagger_route())
        if self.redoc_url:
            routes.append(self._redoc_route())

        # Health check
        routes.append(self._health_route())

        # Register routes with the template engine (if configured) so that
        # url_for() is available inside templates.
        self._routes_snapshot = routes
        try:
            from aura.templates.shortcuts import _engine
            if _engine is not None:
                _engine.register_routes(routes)
        except ImportError:
            pass

        starlette_middleware = self._build_middleware()

        @contextlib.asynccontextmanager
        async def _lifespan(app: Starlette) -> AsyncIterator[None]:
            await self._on_startup()
            try:
                yield
            finally:
                await self._on_shutdown()

        app = Starlette(
            debug=self.debug,
            routes=routes,
            middleware=starlette_middleware,
            lifespan=_lifespan,
            exception_handlers={Exception: exception_handler},
        )
        app.state.container = self.container
        return app

    def _build_middleware(self) -> list[Middleware]:
        """Convert the raw middleware list into Starlette ``Middleware`` objects.

        Returns:
            List of :class:`~starlette.middleware.Middleware` descriptors.
        """
        result: list[Middleware] = []

        # Automatically prepend request DI container scoping middleware
        from aura.middleware.di import DIRequestScopeMiddleware
        result.append(Middleware(DIRequestScopeMiddleware))

        # Automatically append DatabaseMiddleware if SQLAlchemy is available
        # and database is configured
        try:
            from aura.orm.middleware import DatabaseMiddleware

            cfg = self._config_class()
            db_url = cfg.database.url
            if db_url:
                result.append(Middleware(DatabaseMiddleware))
                logger.debug(
                    "DatabaseMiddleware automatically registered via environment configuration"
                )
        except ImportError:
            pass

        for mw in self._global_middleware:
            if isinstance(mw, Middleware):
                result.append(mw)
            elif isinstance(mw, type):
                result.append(Middleware(mw))  # type: ignore[arg-type]
            elif hasattr(mw, "build") or (
                callable(mw) and not isinstance(mw, Middleware)
            ):
                result.append(Middleware(self._factory_middleware_class(mw)))  # type: ignore[arg-type]
            else:
                logger.warning("Skipping unrecognised middleware: %r", mw)
        return result

    @staticmethod
    def _factory_middleware_class(factory: Any) -> type:
        """Wrap factory-style middleware (``build(app)``) for Starlette."""
        build_fn = factory.build if hasattr(factory, "build") else factory

        class _FactoryMiddleware:
            def __init__(self, app: ASGIApp) -> None:
                self.app = build_fn(app)

            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                await self.app(scope, receive, send)

        return _FactoryMiddleware

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def _on_startup(self) -> None:
        """Called by Starlette on application startup.

        Loads the config, registers it as a singleton, and warms up the
        DI container.
        """
        logger.info("Starting %s v%s", self.title, self.version)

        # Instantiate config and register in container
        try:
            cfg = self._config_class()
            self.container.register_instance(self._config_class, cfg)
            logger.debug("Config loaded: %s", _safe_config_dump(cfg))
        except Exception:
            logger.exception("Failed to load config — using defaults")
            cfg = AuraConfig()

        # Initialize logging system
        try:
            from aura.logging import setup_logging
            from aura.logging.config import LogConfig as _LogConfig

            log_config = getattr(cfg, "logging", None) or _LogConfig()
            setup_logging(log_config)
        except Exception:
            logger.exception("Failed to initialize logging system")

        # Auto-initialise the database using the already-loaded config object.
        # cfg.database.url respects aura.toml, .env, and env vars (via pydantic-settings)
        # — same source that _build_middleware() uses, guaranteeing consistency.
        _db_url: str | None = getattr(cfg.database, "url", None)

        if _db_url:
            try:
                from aura.orm.session import db as _db
                if _db._engine is None:
                    _db_echo: bool = getattr(cfg.database, "echo", False)
                    _db.init(_db_url, echo=_db_echo)
                    logger.info("Database auto-initialized: %s (echo=%s)", _db_url, _db_echo)
            except ImportError:
                pass

        # Warm up singletons
        await self.container.startup()

        # Run per-module startup hooks (e.g. AuraTemplateModule.on_startup)
        await self.registry.run_module_startups(self.container, self.debug)

        # After module startups the template engine may have just been set;
        # register the route list with it now if available.
        try:
            from aura.templates.shortcuts import _engine as _tmpl_engine
            routes = getattr(self, "_routes_snapshot", None)
            if _tmpl_engine is not None and routes is not None:
                _tmpl_engine.register_routes(routes)
        except ImportError:
            pass

        logger.info("%s started successfully", self.title)

    async def _on_shutdown(self) -> None:
        """Called by Starlette on application shutdown.

        Releases DI container resources and performs graceful cleanup.
        """
        logger.info("Shutting down %s", self.title)
        await self.container.shutdown()
        logger.info("%s shut down", self.title)

    # ------------------------------------------------------------------
    # Meta routes
    # ------------------------------------------------------------------

    def _openapi_route(self) -> Route:
        """Return a Starlette route that serves the OpenAPI JSON spec."""
        openapi_gen = self.openapi

        async def openapi_endpoint(request: Request) -> JSONResponse:
            return JSONResponse(openapi_gen.generate())

        return Route(
            self.openapi_url or "/openapi.json",
            endpoint=openapi_endpoint,
            methods=["GET"],
            name="openapi",
        )

    def _swagger_route(self) -> Route:
        """Return a Starlette route that serves the Swagger UI HTML page."""
        openapi_url = self.openapi_url or "/openapi.json"
        title = self.title

        async def swagger_endpoint(request: Request) -> HTMLResponse:
            html = _SWAGGER_HTML.replace("{{TITLE}}", title).replace(
                "{{OPENAPI_URL}}", openapi_url
            )
            return HTMLResponse(html)

        return Route(
            self.docs_url or "/docs",
            endpoint=swagger_endpoint,
            methods=["GET"],
            name="swagger_ui",
        )

    def _redoc_route(self) -> Route:
        """Return a Starlette route that serves the Redoc HTML page."""
        openapi_url = self.openapi_url or "/openapi.json"
        title = self.title

        async def redoc_endpoint(request: Request) -> HTMLResponse:
            html = _REDOC_HTML.replace("{{TITLE}}", title).replace(
                "{{OPENAPI_URL}}", openapi_url
            )
            return HTMLResponse(html)

        return Route(
            self.redoc_url or "/redoc",
            endpoint=redoc_endpoint,
            methods=["GET"],
            name="redoc",
        )

    def _health_route(self) -> Route:
        """Return a ``GET /health`` liveness probe route."""
        framework_version = self.version

        async def health_endpoint(request: Request) -> JSONResponse:
            return JSONResponse({"status": "ok", "version": framework_version})

        return Route(
            "/health",
            endpoint=health_endpoint,
            methods=["GET"],
            name="health",
        )

    # ------------------------------------------------------------------
    # Server helpers
    # ------------------------------------------------------------------

    def run(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        reload: bool | None = None,
        workers: int | None = None,
        server: str = "uvicorn",
    ) -> None:
        """Start the HTTP server programmatically.

        This is a convenience method for development.  In production, use
        your ASGI server directly (Granian, Uvicorn, Hypercorn, etc.).

        Args:
            host: Bind address.  Falls back to ``AuraConfig.server.host``.
            port: TCP port.  Falls back to ``AuraConfig.server.port``.
            reload: Enable file-watcher auto-reload.
            workers: Number of worker processes.
            server: Server backend — ``"uvicorn"`` (default) or ``"granian"``.

        Raises:
            ImportError: If the requested server package is not installed.
        """
        try:
            cfg = self._config_class()
        except Exception:
            cfg = AuraConfig()

        _host = host or cfg.server.host
        _port = port or cfg.server.port
        _reload = reload if reload is not None else cfg.server.reload
        _workers = workers or cfg.server.workers

        if server == "granian":
            self._run_granian(_host, _port, _reload, _workers)
        else:
            self._run_uvicorn(_host, _port, _reload, _workers)

    def _run_uvicorn(
        self,
        host: str,
        port: int,
        reload: bool,
        workers: int,
    ) -> None:
        """Start the server using Uvicorn.

        Args:
            host: Bind address.
            port: TCP port.
            reload: Enable auto-reload.
            workers: Number of worker processes.
        """
        try:
            import uvicorn
        except ImportError as exc:
            raise ImportError(
                "uvicorn is not installed. Run: pip install aura-framework[uvicorn]"
            ) from exc

        uvicorn.run(
            self,
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,
            log_level="debug" if self.debug else "info",
        )

    def _run_granian(
        self,
        host: str,
        port: int,
        reload: bool,
        workers: int,
    ) -> None:
        """Start the server using Granian.

        Args:
            host: Bind address.
            port: TCP port.
            reload: Enable auto-reload.
            workers: Number of worker processes.
        """
        try:
            from granian import Granian
        except ImportError as exc:
            raise ImportError(
                "granian is not installed. Run: pip install aura-framework[granian]"
            ) from exc

        Granian(
            target=cast(Any, self),
            address=host,
            port=port,
            workers=workers,
            reload=reload,
            interface=cast(Any, "asgi"),
        ).serve()


# ---------------------------------------------------------------------------
# HTML templates for docs
# ---------------------------------------------------------------------------

_SWAGGER_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>{{TITLE}} — Swagger UI</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" >
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    const ui = SwaggerUIBundle({
      url: "{{OPENAPI_URL}}",
      dom_id: "#swagger-ui",
      presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
      layout: "StandaloneLayout",
      deepLinking: true,
    })
  </script>
</body>
</html>"""

_REDOC_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>{{TITLE}} — ReDoc</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700"
        rel="stylesheet">
  <style>body { margin: 0; padding: 0; }</style>
</head>
<body>
  <redoc spec-url="{{OPENAPI_URL}}"></redoc>
  <script src="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"></script>
</body>
</html>"""

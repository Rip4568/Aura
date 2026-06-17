"""Middleware managing request-scoped database transactions and DI session binding."""

from __future__ import annotations

import logging

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("aura.orm.middleware")

try:
    from sqlalchemy.ext.asyncio import AsyncSession

    from aura.orm.session import db

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


class DatabaseMiddleware:
    """Middleware managing request-scoped database transactions and registering
    the active transactional AsyncSession into the request's scoped container.
    """

    def __init__(self, app: ASGIApp) -> None:
        if not SQLALCHEMY_AVAILABLE:
            raise RuntimeError(
                "DatabaseMiddleware requires SQLAlchemy. "
                "Please install it with: pip install 'aura-web[sqlalchemy]'"
            )
        self.app = app
        self._init_attempted = False
        self._lazy_init_failed = False

    def _try_lazy_init(self) -> None:
        """Attempt to auto-initialize the database from config.

        This is a fallback for environments where lifespan events are not
        triggered (Starlette TestClient, httpx ASGITransport, uvicorn
        --lifespan off).  On normal uvicorn startup, _on_startup() in
        app.py handles initialization and this method becomes a no-op
        because db._engine is already set.
        """
        try:
            from aura.config.base import AuraConfig

            cfg = AuraConfig()
            db_url = cfg.database.url
            if db_url and db._engine is None:
                db.init(db_url, echo=cfg.database.echo)
                logger.info(
                    "Database lazy-initialized on first request: %s (echo=%s)",
                    db_url,
                    cfg.database.echo,
                )
        except ImportError:
            pass
        except Exception:
            logger.exception("Failed to lazy-initialize database")
            self._lazy_init_failed = True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # If database is not configured, try lazy-initializing it on the
        # first request.  This covers scenarios where lifespan events are
        # not triggered: TestClient, AuraTestClient, uvicorn --lifespan off.
        if not SQLALCHEMY_AVAILABLE or db._session_factory is None:
            if db._session_factory is None and not self._init_attempted:
                self._init_attempted = True
                self._try_lazy_init()

            # Fail-fast if lazy init was attempted and failed
            if self._lazy_init_failed and db._session_factory is None:
                logger.error(
                    "DatabaseMiddleware: lazy-initialization failed and "
                    "db._session_factory is None. Cannot process request."
                )
                # Return 500 Service Unavailable
                await send({
                    "type": "http.response.start",
                    "status": 500,
                    "headers": [(b"content-type", b"text/plain")],
                })
                await send({
                    "type": "http.response.body",
                    "body": (
                        b"Service Unavailable: Database initialization failed.\n"
                        b"Set AURA__DATABASE__URL env var or configure "
                        b"[database] url in aura.toml."
                    ),
                })
                return

            if db._session_factory is None:
                logger.warning(
                    "DatabaseMiddleware is active but db._session_factory is None. "
                    "Database operations will fail. "
                    "Set AURA__DATABASE__URL env var or configure "
                    "[database] url in aura.toml."
                )
            await self.app(scope, receive, send)
            return

        scoped_container = scope.get("state", {}).get("container")

        # Automatically open, commit, rollback, and close database session
        async with db.session() as session:
            # Store in local state for backwards compatibility
            scope.setdefault("state", {})["db_session"] = session

            # Option C: Set the active session in the ContextVar for singleton repositories
            from aura.orm.session import current_session
            token = current_session.set(session)

            try:
                if scoped_container is not None:
                    # Dynamically register request's active session inside scoped sub-container
                    scoped_container.register_instance(AsyncSession, session)
                    logger.debug("Registered request-scoped AsyncSession in DI container.")

                await self.app(scope, receive, send)
            finally:
                # Always reset context variable to prevent leakage
                current_session.reset(token)

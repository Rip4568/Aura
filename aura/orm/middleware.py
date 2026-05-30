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

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # If database is not configured, bypass and continue
        if not SQLALCHEMY_AVAILABLE or db._session_factory is None:
            await self.app(scope, receive, send)
            return

        scoped_container = scope.get("state", {}).get("container")

        # Automatically open, commit, rollback, and close database session
        async with db.session() as session:
            # Store in local state for backwards compatibility
            scope.setdefault("state", {})["db_session"] = session

            if scoped_container is not None:
                # Dynamically register request's active session inside scoped sub-container
                scoped_container.register_instance(AsyncSession, session)
                logger.debug("Registered request-scoped AsyncSession in DI container.")

            await self.app(scope, receive, send)

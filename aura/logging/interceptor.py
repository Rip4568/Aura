"""ASGI middleware for request logging with context propagation."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from aura.logging.context import clear_context, set_request_id
from aura.logging.logger import Log


class RequestLogInterceptor:
    """ASGI middleware for automatic request logging and context propagation.

    This middleware:
    1. Extracts request ID from a configured header (default: x-request-id)
    2. Sets the request ID in context variables for all logs in that request
    3. Optionally extracts user ID from headers or request state
    4. Clears context after request completes

    Args:
        app: The ASGI application to wrap.
        extract_request_id_header: Header name to extract request ID from.
                                   (default: "x-request-id")
        log_headers: If True, log request headers at DEBUG level.
        generate_request_id: If True and header not present, generate a UUID.
    """

    def __init__(
        self,
        app: Callable[[Any, Any, Any], Awaitable[Any]],
        extract_request_id_header: str = "x-request-id",
        log_headers: bool = False,
        generate_request_id: bool = True,
    ) -> None:
        """Initialize the RequestLogInterceptor middleware.

        Args:
            app: ASGI application.
            extract_request_id_header: Header to extract request ID from.
            log_headers: Log request headers at DEBUG level.
            generate_request_id: Generate UUID if header not present.
        """
        self.app = app
        self.extract_request_id_header = extract_request_id_header.lower()
        self.log_headers = log_headers
        self.generate_request_id = generate_request_id

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Any],
        send: Callable[[dict[str, Any]], Any],
    ) -> None:
        """Process an ASGI message.

        Args:
            scope: ASGI scope dict.
            receive: ASGI receive callable.
            send: ASGI send callable.
        """
        if scope["type"] != "http":
            # Non-HTTP requests pass through untouched
            await self.app(scope, receive, send)
            return

        # Extract headers
        headers = {
            name.decode().lower(): value.decode()
            for name, value in scope.get("headers", [])
        }

        # Extract or generate request ID
        request_id = headers.get(self.extract_request_id_header)
        if not request_id:
            if self.generate_request_id:
                request_id = str(uuid.uuid4())
            else:
                request_id = "unknown"

        # Set context
        set_request_id(request_id)

        # Log headers if enabled
        if self.log_headers:
            Log.debug("Request headers", headers=headers)

        try:
            # Call wrapped app
            await self.app(scope, receive, send)
        finally:
            # Clear context
            clear_context()

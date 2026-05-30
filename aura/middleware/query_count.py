"""QueryCountMiddleware — adds X-Query-Count header per request."""
from __future__ import annotations

import os
import re
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send


class QueryCountMiddleware:
    """Adds query-count headers to HTTP responses.

    Headers added:
      - ``X-Query-Count: N``      — total queries executed in the request
      - ``X-Query-Time-Ms: N.N``  — total time spent in queries (ms)
      - ``X-Query-N1-Risk: N``    — number of duplicate SQL patterns (N+1 candidates)

    Only active when ``AURA__DEBUG=true`` by default. Pass ``only_debug=False``
    to enable in all environments (useful for monitoring dashboards).

    Usage::

        app = Aura(modules=[AppModule])
        app.add_middleware(QueryCountMiddleware)          # debug only
        app.add_middleware(QueryCountMiddleware, only_debug=False)  # always on
    """

    def __init__(self, app: ASGIApp, *, only_debug: bool = True) -> None:
        self.app = app
        self.only_debug = only_debug

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if self.only_debug and not _debug_enabled():
            await self.app(scope, receive, send)
            return

        try:
            from aura.orm.profiling import query_log
        except ImportError:
            await self.app(scope, receive, send)
            return

        async with query_log() as log:
            async def send_with_headers(message: Any) -> None:
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"x-query-count", str(log.count).encode()))
                    headers.append((b"x-query-time-ms", f"{log.total_ms:.1f}".encode()))
                    n1 = len({_fingerprint(q.sql) for q in log.duplicates()})
                    if n1:
                        headers.append((b"x-query-n1-risk", str(n1).encode()))
                    message = {**message, "headers": headers}
                await send(message)

            await self.app(scope, receive, send_with_headers)


def _debug_enabled() -> bool:
    return os.environ.get("AURA__DEBUG", "").lower() in ("1", "true", "yes")


def _fingerprint(sql: str) -> str:
    sql = re.sub(r"'[^']*'|\b\d+\b", "?", sql)
    return re.sub(r"\s+", " ", sql).strip().upper()

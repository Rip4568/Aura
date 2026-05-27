"""HTML response types for the Aura template system."""

from __future__ import annotations

from typing import Any

from starlette.responses import HTMLResponse as StarletteHTMLResponse

from aura.templates.htmx import HtmxResponseHeaders


class HtmlResponse(StarletteHTMLResponse):
    """An HTML response with optional htmx control headers.

    Returned by route handlers that render templates.  Carries a
    :class:`~aura.templates.htmx.HtmxResponseHeaders` builder so you can
    attach htmx directives fluently::

        response = HtmlResponse("<p>Hello</p>")
        response.htmx.trigger("itemSaved").push_url("/items")
        return response

    Args:
        content: The rendered HTML string.
        status_code: HTTP status code (default 200).
        headers: Extra HTTP headers.
        media_type: Content-Type header (default ``"text/html"``).
    """

    def __init__(
        self,
        content: str = "",
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        media_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.htmx = HtmxResponseHeaders()
        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
        )

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """Merge htmx headers before sending the response."""
        htmx_headers = self.htmx.to_dict()
        if htmx_headers:
            self.headers.update(htmx_headers)
        await super().__call__(scope, receive, send)

"""Decorators for HTML-rendering routes and server-sent events.

The ``@html`` decorator marks a route as returning an HTML response instead of
JSON.  It integrates with the Aura routing system so that:

  - The handler return value is passed through the template engine.
  - htmx partial renders are detected automatically.
  - Response headers (``Content-Type``, htmx ``HX-*``) are set correctly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def html(
    path: str,
    *,
    template: str | None = None,
    status: int = 200,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for GET routes that render HTML templates.

    Works exactly like :func:`~aura.routing.decorators.get` but sets
    ``response_type="html"`` so the router wraps the result with
    :class:`~aura.templates.response.HtmlResponse`.

    Args:
        path: URL path pattern.
        template: Default template name.  If the handler returns a
            :class:`~aura.templates.context.TemplateContext`, this template
            is used for rendering.  If the handler already returns an
            :class:`~aura.templates.response.HtmlResponse`, this is ignored.
        status: HTTP status code (default 200).
        tags: OpenAPI tags.
        summary: Short summary for docs.
        description: Long Markdown description.
        guards: Per-route guards.

    Example::

        class HomeController:
            @html("/", template="home.html")
            async def home(self) -> HomeContext:
                return HomeContext(title="Home", ...)

            @html("/users", template="users/list.html")
            async def user_list(self) -> UserListContext:
                users = await self.service.list()
                return UserListContext(users=users, total=len(users))

    If you need full control (partial renders, htmx, etc.) return an
    :class:`~aura.templates.response.HtmlResponse` directly::

        @html("/users/{id}")
        async def user_detail(
            self,
            id: Annotated[int, Param()],
            request: AuraRequest,
        ) -> HtmlResponse:
            user = await self.service.get(id)
            ctx = UserDetailContext(user=user)
            if request.htmx.is_htmx:
                return await render("partials/user_detail.html", ctx)
            return await render("users/detail.html", ctx)
    """
    def decorator(func: F) -> F:
        meta = {
            "method": "GET",
            "path": path,
            "response": None,
            "status": status,
            "tags": tags or [],
            "summary": summary or func.__name__.replace("_", " ").title(),
            "description": description or func.__doc__ or "",
            "deprecated": False,
            "guards": guards or [],
            "middleware": [],
            "response_type": "html",
            "template": template,
        }
        func.__aura_route__ = meta  # type: ignore[attr-defined]
        return func

    return decorator


def sse(
    path: str,
    *,
    tags: list[str] | None = None,
    summary: str | None = None,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for Server-Sent Events (SSE) endpoints.

    The handler must be an async generator that yields strings or dicts.
    Dicts are serialised to JSON and sent as SSE ``data:`` lines.

    Args:
        path: URL path pattern.
        tags: OpenAPI tags.
        summary: Short summary for docs.
        guards: Per-route guards.

    Example::

        @sse("/events/live")
        async def live_feed(self) -> AsyncGenerator[dict, None]:
            async for event in event_bus.subscribe():
                yield {"type": event.type, "data": event.payload}
    """

    def decorator(func: F) -> F:
        func.__aura_route__ = {  # type: ignore[attr-defined]
            "method": "GET",
            "path": path,
            "response": None,
            "status": 200,
            "tags": tags or [],
            "summary": summary or func.__name__.replace("_", " ").title(),
            "description": func.__doc__ or "",
            "deprecated": False,
            "guards": guards or [],
            "middleware": [],
            "response_type": "sse",
        }
        return func

    return decorator

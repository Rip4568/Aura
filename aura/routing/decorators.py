"""Route decorators for the Aura framework."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def _route_decorator(
    method: str,
    path: str,
    *,
    response: type | None = None,
    status: int = 200,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    guards: list[Any] | None = None,
    middleware: list[Any] | None = None,
) -> Callable[[F], F]:
    """Internal factory used by all HTTP method decorators.

    Args:
        method: HTTP verb in upper case (``"GET"``, ``"POST"``, etc.).
        path: URL path pattern (e.g. ``"/users/{user_id}"``).
        response: Pydantic schema class for the success response body.
        status: HTTP status code for the success response.
        tags: OpenAPI tags used to group endpoints in the docs.
        summary: Short description shown in the docs.
        description: Longer Markdown description shown in the docs.
        deprecated: Mark the endpoint as deprecated in the spec.
        guards: Per-route guards; evaluated after global/module guards.
        middleware: Per-route middleware callables.

    Returns:
        A decorator that attaches ``__aura_route__`` metadata to the function.
    """

    def decorator(func: F) -> F:
        func.__aura_route__ = {  # type: ignore[attr-defined]
            "method": method,
            "path": path,
            "response": response,
            "status": status,
            "tags": tags or [],
            "summary": summary or func.__name__.replace("_", " ").title(),
            "description": description or func.__doc__ or "",
            "deprecated": deprecated,
            "guards": guards or [],
            "middleware": middleware or [],
        }
        return func

    return decorator


def get(
    path: str,
    *,
    response: type | None = None,
    status: int = 200,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for HTTP GET routes.

    Args:
        path: URL path pattern.
        response: Pydantic schema for the response body.
        status: HTTP status code (default 200).
        tags: OpenAPI tags.
        summary: Short summary for docs.
        description: Long Markdown description for docs.
        deprecated: Whether to mark as deprecated in OpenAPI spec.
        guards: List of guard instances applied to this route.

    Example::

        @get("/users/{user_id}", response=UserResponse)
        async def get_user(user_id: Param[int]) -> UserResponse:
            ...
    """
    return _route_decorator(
        "GET", path,
        response=response, status=status, tags=tags,
        summary=summary, description=description,
        deprecated=deprecated, guards=guards,
    )


def post(
    path: str,
    *,
    response: type | None = None,
    status: int = 201,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for HTTP POST routes (default status 201).

    Args:
        path: URL path pattern.
        response: Pydantic schema for the response body.
        status: HTTP status code (default 201).
        tags: OpenAPI tags.
        summary: Short summary for docs.
        description: Long Markdown description.
        deprecated: Whether to mark as deprecated.
        guards: Per-route guards.
    """
    return _route_decorator(
        "POST", path,
        response=response, status=status, tags=tags,
        summary=summary, description=description,
        deprecated=deprecated, guards=guards,
    )


def put(
    path: str,
    *,
    response: type | None = None,
    status: int = 200,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for HTTP PUT routes.

    Args:
        path: URL path pattern.
        response: Pydantic schema for the response body.
        status: HTTP status code (default 200).
        tags: OpenAPI tags.
        summary: Short summary for docs.
        description: Long Markdown description.
        deprecated: Whether to mark as deprecated.
        guards: Per-route guards.
    """
    return _route_decorator(
        "PUT", path,
        response=response, status=status, tags=tags,
        summary=summary, description=description,
        deprecated=deprecated, guards=guards,
    )


def delete(
    path: str,
    *,
    response: type | None = None,
    status: int = 204,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for HTTP DELETE routes (default status 204).

    Args:
        path: URL path pattern.
        response: Pydantic schema for the response body.
        status: HTTP status code (default 204).
        tags: OpenAPI tags.
        summary: Short summary for docs.
        description: Long Markdown description.
        deprecated: Whether to mark as deprecated.
        guards: Per-route guards.
    """
    return _route_decorator(
        "DELETE", path,
        response=response, status=status, tags=tags,
        summary=summary, description=description,
        deprecated=deprecated, guards=guards,
    )


def patch(
    path: str,
    *,
    response: type | None = None,
    status: int = 200,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    deprecated: bool = False,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for HTTP PATCH routes.

    Args:
        path: URL path pattern.
        response: Pydantic schema for the response body.
        status: HTTP status code (default 200).
        tags: OpenAPI tags.
        summary: Short summary for docs.
        description: Long Markdown description.
        deprecated: Whether to mark as deprecated.
        guards: Per-route guards.
    """
    return _route_decorator(
        "PATCH", path,
        response=response, status=status, tags=tags,
        summary=summary, description=description,
        deprecated=deprecated, guards=guards,
    )


def ws(
    path: str,
    *,
    tags: list[str] | None = None,
    summary: str | None = None,
    description: str | None = None,
    guards: list[Any] | None = None,
) -> Callable[[F], F]:
    """Decorator for WebSocket routes.

    Args:
        path: URL path pattern.
        tags: OpenAPI tags.
        summary: Short summary for docs.
        description: Long Markdown description.
        guards: Per-route guards.

    Example::

        @ws("/ws/chat")
        async def chat_endpoint(websocket: WebSocket) -> None:
            await websocket.accept()
            ...
    """
    return _route_decorator(
        "WS", path,
        tags=tags, summary=summary, description=description, guards=guards,
    )

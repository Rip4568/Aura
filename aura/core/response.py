"""Aura response helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from starlette.responses import JSONResponse, Response


class AuraResponse(JSONResponse):
    """
    JSON response with Aura conventions.

    Automatically serialises Pydantic models via ``model_dump(mode="json")``
    and sets the ``Content-Type: application/json`` header.

    Args:
        content: Response body.  May be a Pydantic model, a plain dict/list,
            or any JSON-serialisable value.
        status_code: HTTP status code.
        headers: Additional response headers.
    """

    def __init__(
        self,
        content: Any = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        if isinstance(content, BaseModel):
            content = content.model_dump(mode="json")
        super().__init__(content=content, status_code=status_code, headers=headers, **kwargs)


def ok(content: Any = None, status: int = 200) -> AuraResponse:
    """Shorthand for a successful JSON response.

    Args:
        content: Response body.
        status: HTTP status code (default 200).

    Returns:
        An :class:`AuraResponse` with the given content and status.
    """
    return AuraResponse(content=content, status_code=status)


def created(content: Any = None) -> AuraResponse:
    """Shorthand for a 201 Created response.

    Args:
        content: Response body.

    Returns:
        An :class:`AuraResponse` with status 201.
    """
    return AuraResponse(content=content, status_code=201)


def no_content() -> Response:
    """Shorthand for a 204 No Content response.

    Returns:
        An empty :class:`~starlette.responses.Response` with status 204.
    """
    return Response(status_code=204)


def _is_safe_redirect_url(url: str) -> bool:
    """Allow only same-application relative paths (no open redirects)."""
    if not url.startswith("/"):
        return False
    if url.startswith("//"):
        return False
    return "\\" not in url


def redirect(url: str, permanent: bool = False) -> Response:
    """Shorthand for a redirect response.

    Only relative paths starting with ``/`` are allowed to prevent open redirects.

    Args:
        url: The URL to redirect to.
        permanent: Use 308 (permanent) instead of 307 (temporary).

    Returns:
        A :class:`~starlette.responses.Response` with the ``Location`` header set.

    Raises:
        BadRequestException: If *url* is not a safe relative path.
    """
    from aura.exceptions.http import BadRequestException

    if not _is_safe_redirect_url(url):
        raise BadRequestException(
            "Redirect URL must be a relative path starting with '/'"
        )
    status_code = 308 if permanent else 307
    return Response(
        status_code=status_code,
        headers={"Location": url},
    )

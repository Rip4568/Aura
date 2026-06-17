"""HTTP exception hierarchy for the Aura framework."""

from __future__ import annotations

from typing import Any

from aura.exceptions.base import AuraException


class HTTPException(AuraException):
    """
    Base class for all HTTP exceptions.

    Raising an :class:`HTTPException` inside a route handler causes the
    framework to respond with the appropriate HTTP status code and a
    structured JSON body.

    Attributes:
        status_code: HTTP status code (e.g. 404, 422).
        message: Human-readable error message sent to the client.
        code: Optional machine-readable error code.
        detail: Arbitrary extra information included in the response body.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        code: str | None = None,
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message, code=code, detail=detail)
        self.status_code = status_code
        self.headers = headers or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception to a JSON-serialisable dictionary."""
        payload: dict[str, Any] = {
            "error": {
                "status": self.status_code,
                "message": self.message,
            }
        }
        if self.code:
            payload["error"]["code"] = self.code
        if self.detail is not None:
            payload["error"]["detail"] = self.detail
        return payload

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status_code={self.status_code}, "
            f"message={self.message!r})"
        )


# ---------------------------------------------------------------------------
# 4xx Client Errors
# ---------------------------------------------------------------------------


class BadRequestException(HTTPException):
    """400 Bad Request — the server cannot process the request due to a client error."""

    def __init__(
        self,
        message: str = "Bad request",
        *,
        code: str | None = "BAD_REQUEST",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(400, message, code=code, detail=detail, headers=headers)


class UnauthorizedException(HTTPException):
    """401 Unauthorized — authentication is required and has failed or not been provided."""

    def __init__(
        self,
        message: str = "Unauthorized",
        *,
        code: str | None = "UNAUTHORIZED",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(401, message, code=code, detail=detail, headers=headers)


class ForbiddenException(HTTPException):
    """403 Forbidden — the client does not have access rights to the content."""

    def __init__(
        self,
        message: str = "Forbidden",
        *,
        code: str | None = "FORBIDDEN",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(403, message, code=code, detail=detail, headers=headers)


class NotFoundException(HTTPException):
    """404 Not Found — the requested resource could not be found."""

    def __init__(
        self,
        message: str = "Not found",
        *,
        code: str | None = "NOT_FOUND",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(404, message, code=code, detail=detail, headers=headers)


class MethodNotAllowedException(HTTPException):
    """405 Method Not Allowed — the HTTP method is not supported for this resource."""

    def __init__(
        self,
        message: str = "Method not allowed",
        *,
        code: str | None = "METHOD_NOT_ALLOWED",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(405, message, code=code, detail=detail, headers=headers)


class ConflictException(HTTPException):
    """409 Conflict — the request conflicts with the current state of the resource."""

    def __init__(
        self,
        message: str = "Conflict",
        *,
        code: str | None = "CONFLICT",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(409, message, code=code, detail=detail, headers=headers)


class UnprocessableEntityException(HTTPException):
    """422 Unprocessable Entity — the request is well-formed but contains semantic errors."""

    def __init__(
        self,
        message: str = "Unprocessable entity",
        *,
        code: str | None = "UNPROCESSABLE_ENTITY",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(422, message, code=code, detail=detail, headers=headers)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to FastAPI-compatible ``{detail: [{loc, msg, type}]}`` format."""
        if isinstance(self.detail, list):
            return {"detail": self.detail}
        if self.detail is not None:
            return {
                "detail": [
                    {
                        "loc": ["body"],
                        "msg": str(self.detail),
                        "type": "value_error",
                    }
                ]
            }
        return {
            "detail": [
                {
                    "loc": [],
                    "msg": self.message,
                    "type": "value_error",
                }
            ]
        }


class TooManyRequestsException(HTTPException):
    """429 Too Many Requests — the client has sent too many requests in a given time window."""

    def __init__(
        self,
        message: str = "Too many requests",
        *,
        code: str | None = "TOO_MANY_REQUESTS",
        detail: Any = None,
        retry_after: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        extra_headers = dict(headers or {})
        if retry_after is not None:
            extra_headers["Retry-After"] = str(retry_after)
        super().__init__(429, message, code=code, detail=detail, headers=extra_headers)


# ---------------------------------------------------------------------------
# 5xx Server Errors
# ---------------------------------------------------------------------------


class InternalServerException(HTTPException):
    """500 Internal Server Error — an unexpected condition was encountered."""

    def __init__(
        self,
        message: str = "Internal server error",
        *,
        code: str | None = "INTERNAL_SERVER_ERROR",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(500, message, code=code, detail=detail, headers=headers)


class ServiceUnavailableException(HTTPException):
    """503 Service Unavailable — the server is temporarily unable to handle requests."""

    def __init__(
        self,
        message: str = "Service unavailable",
        *,
        code: str | None = "SERVICE_UNAVAILABLE",
        detail: Any = None,
        retry_after: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        extra_headers = dict(headers or {})
        if retry_after is not None:
            extra_headers["Retry-After"] = str(retry_after)
        super().__init__(503, message, code=code, detail=detail, headers=extra_headers)


class GatewayTimeoutException(HTTPException):
    """504 Gateway Timeout — the upstream server failed to send a response in time."""

    def __init__(
        self,
        message: str = "Gateway timeout",
        *,
        code: str | None = "GATEWAY_TIMEOUT",
        detail: Any = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(504, message, code=code, detail=detail, headers=headers)

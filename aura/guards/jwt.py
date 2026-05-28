"""JWTGuard — validates Bearer tokens and populates request.state.user."""
from __future__ import annotations

from typing import Any

from starlette.requests import Request

from aura.guards.base import Guard
from aura.exceptions.http import UnauthorizedException


class JWTGuard(Guard):
    """Validates a JWT Bearer token on every request.

    Populates ``request.state.user`` with the decoded token payload if valid.
    Raises ``UnauthorizedException`` (401) with ``WWW-Authenticate: Bearer`` if invalid.

    Usage::

        guard = JWTGuard(secret="my-secret", algorithm="HS256")

        @get("/me", guards=[guard])
        async def get_me(self, request: AuraRequest) -> UserResponse:
            user = request.state.user  # dict with token payload
            ...

        # Module-wide:
        @Module(guards=[guard], ...)
        class SecureModule: ...

    Args:
        secret: The secret key (HS256) or public key (RS256) to verify the token.
        algorithm: JWT algorithm. Default: ``"HS256"``.
        auto_error: If ``True`` (default), raises 401 on failure. If ``False``, sets
                    ``request.state.user = None`` and allows the request through.
    """

    def __init__(
        self,
        *,
        secret: str,
        algorithm: str = "HS256",
        auto_error: bool = True,
    ) -> None:
        self.secret = secret
        self.algorithm = algorithm
        self.auto_error = auto_error

    async def can_activate(self, request: Request) -> bool:
        token = self._extract_token(request)
        if token is None:
            if self.auto_error:
                raise UnauthorizedException(
                    "Missing Bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            request.state.user = None
            return True

        payload = self._decode(token)
        if payload is None:
            if self.auto_error:
                raise UnauthorizedException(
                    "Invalid or expired token",
                    headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
                )
            request.state.user = None
            return True

        request.state.user = payload
        return True

    def _extract_token(self, request: Request) -> str | None:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:]
        return None

    def _decode(self, token: str) -> dict[str, Any] | None:
        try:
            from jose import jwt, JWTError  # noqa: F401

            return dict(jwt.decode(token, self.secret, algorithms=[self.algorithm]))
        except Exception:
            return None

    async def on_denied(self, request: Request) -> None:
        raise UnauthorizedException(
            "Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )

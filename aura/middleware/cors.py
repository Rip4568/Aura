"""CORS middleware for Aura — thin wrapper around Starlette's CORSMiddleware."""

from __future__ import annotations

from typing import Any, Sequence


class CORSMiddleware:
    """Configurable CORS (Cross-Origin Resource Sharing) middleware.

    Wraps ``starlette.middleware.cors.CORSMiddleware`` with sensible defaults
    and a clean Aura-native API.

    Args:
        allow_origins: List of allowed origin strings.  Use ``["*"]`` to
                       allow all origins (not recommended for production).
        allow_methods: Allowed HTTP methods.
        allow_headers: Allowed request headers.
        allow_credentials: Allow cookies / ``Authorization`` headers.
        expose_headers: Headers to expose to the browser.
        max_age: How long (seconds) the preflight response may be cached.

    Example::

        app = Aura(
            middleware=[
                CORSMiddleware(
                    allow_origins=["https://example.com"],
                    allow_credentials=True,
                )
            ]
        )
    """

    def __init__(
        self,
        allow_origins: Sequence[str] = ("*",),
        allow_methods: Sequence[str] = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"),
        allow_headers: Sequence[str] = ("*",),
        allow_credentials: bool = False,
        expose_headers: Sequence[str] = (),
        max_age: int = 600,
    ) -> None:
        self.allow_origins = list(allow_origins)
        self.allow_methods = list(allow_methods)
        self.allow_headers = list(allow_headers)
        self.allow_credentials = allow_credentials
        self.expose_headers = list(expose_headers)
        self.max_age = max_age

    def build(self, app: Any) -> Any:
        """Wrap *app* with the Starlette CORS middleware.

        Args:
            app: The ASGI application to wrap.

        Returns:
            A new ASGI application with CORS handling applied.
        """
        try:
            from starlette.middleware.cors import CORSMiddleware as StarletteCORS
        except ImportError as exc:
            raise ImportError(
                "starlette is required for CORSMiddleware. "
                "It is included in aura-framework dependencies."
            ) from exc

        return StarletteCORS(
            app=app,
            allow_origins=self.allow_origins,
            allow_methods=self.allow_methods,
            allow_headers=self.allow_headers,
            allow_credentials=self.allow_credentials,
            expose_headers=self.expose_headers,
            max_age=self.max_age,
        )

    def __call__(self, app: Any) -> Any:
        """Alias for :meth:`build` — allows using the instance as a decorator."""
        return self.build(app)

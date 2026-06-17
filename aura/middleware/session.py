"""SessionMiddleware — signed cookie sessions for Aura."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

# ASGI type aliases
Scope = dict[str, Any]
Receive = Callable[[], Any]
Send = Callable[[dict[str, Any]], Any]


class SessionMiddleware:
    """Signed-cookie session middleware.

    Stores session data in a signed, base64-encoded cookie. The session is
    automatically loaded on each request and saved on each response.

    Requires: ``pip install "aura-web[session]"``

    Usage::

        app = Aura(
            middleware=[
                SessionMiddleware(secret_key="change-me-in-production"),
            ]
        )

        # In a route handler:
        @get("/")
        async def index(self, request: AuraRequest) -> dict:
            visits = request.state.session.get("visits", 0) + 1
            request.state.session["visits"] = visits
            return {"visits": visits}

    Args:
        secret_key: Key used to sign the cookie. Must be kept secret.
        session_cookie: Cookie name. Default: ``"session"``.
        max_age: Cookie max-age in seconds. Default: 14 days.
        same_site: SameSite cookie attribute. Default: ``"lax"``.
        https_only: If ``True``, sets the Secure cookie flag.
    """

    def __init__(
        self,
        app: Any,
        *,
        secret_key: str,
        session_cookie: str = "session",
        max_age: int = 14 * 24 * 60 * 60,
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        try:
            from itsdangerous import TimestampSigner  # noqa: F401
        except ImportError:
            raise ImportError(
                "SessionMiddleware requires itsdangerous. "
                'Install with: pip install "aura-web[session]"'
            )
        self.app = app
        self.secret_key = secret_key
        self.session_cookie = session_cookie
        self.max_age = max_age
        self.same_site = same_site
        self.https_only = https_only

    def _load_session(self, headers: list[tuple[bytes, bytes]]) -> dict[str, Any]:
        """Decode session from Cookie header."""
        import json  # noqa: F401

        from itsdangerous import BadSignature, URLSafeTimedSerializer

        serializer = URLSafeTimedSerializer(self.secret_key)
        for name, value in headers:
            if name.lower() == b"cookie":
                cookies = value.decode()
                for part in cookies.split(";"):
                    part = part.strip()
                    if part.startswith(f"{self.session_cookie}="):
                        cookie_value = part[len(self.session_cookie) + 1:]
                        try:
                            data = serializer.loads(cookie_value, max_age=self.max_age)
                            return dict(data) if isinstance(data, dict) else {}
                        except (BadSignature, Exception):
                            return {}
        return {}

    def _save_session(self, session: dict[str, Any]) -> str:
        """Encode session to cookie value."""
        from itsdangerous import URLSafeTimedSerializer

        serializer = URLSafeTimedSerializer(self.secret_key)
        return str(serializer.dumps(session))

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http",):
            await self.app(scope, receive, send)
            return

        # Load session into scope state
        session = self._load_session(scope.get("headers", []))
        initial_session = dict(session)
        scope.setdefault("state", {})["session"] = session

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                current_session = scope["state"].get("session", {})
                if current_session != initial_session:
                    cookie_value = self._save_session(current_session)
                    cookie_str = (
                        f"{self.session_cookie}={cookie_value}; "
                        f"Path=/; Max-Age={self.max_age}; "
                        f"SameSite={self.same_site}; HttpOnly"
                    )
                    if self.https_only:
                        cookie_str += "; Secure"
                    headers = list(message.get("headers", []))
                    headers.append((b"set-cookie", cookie_str.encode()))
                    message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)

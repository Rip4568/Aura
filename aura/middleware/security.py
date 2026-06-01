"""Security headers middleware for Aura — Content Security Policy and protection headers."""

from __future__ import annotations

from typing import Any


class SecurityHeadersMiddleware:
    """Middleware that injects standard security headers into outgoing HTTP responses.

    Protects the application against Clickjacking, MIME Sniffing, Cross-Site Scripting (XSS),
    and other web-based vulnerabilities by default.

    Args:
        app: The ASGI application to wrap.
        content_security_policy: Content-Security-Policy header value (default: None).
        x_frame_options: X-Frame-Options header value (default: 'DENY').
        x_content_type_options: X-Content-Type-Options header value (default: 'nosniff').
        x_xss_protection: X-XSS-Protection header value (default: '0').
        referrer_policy: Referrer-Policy header value (default: 'strict-origin-when-cross-origin').
        hsts_max_age: Strict-Transport-Security max-age in seconds (default: None).
        hsts_include_subdomains: If True, appends 'includeSubDomains' to HSTS (default: True).

    Example::

        from starlette.middleware import Middleware

        app = Aura(
            middleware=[
                Middleware(
                    SecurityHeadersMiddleware,
                    x_frame_options="SAMEORIGIN",
                ),
            ]
        )
    """

    def __init__(
        self,
        app: Any,
        content_security_policy: str | None = None,
        x_frame_options: str = "DENY",
        x_content_type_options: str = "nosniff",
        x_xss_protection: str = "0",
        referrer_policy: str = "strict-origin-when-cross-origin",
        hsts_max_age: int | None = None,
        hsts_include_subdomains: bool = True,
    ) -> None:
        self.app = app
        self.headers: list[tuple[bytes, bytes]] = []

        if content_security_policy is not None:
            self.headers.append((b"content-security-policy", content_security_policy.encode("latin-1")))
        if x_frame_options:
            self.headers.append((b"x-frame-options", x_frame_options.encode("latin-1")))
        if x_content_type_options:
            self.headers.append((b"x-content-type-options", x_content_type_options.encode("latin-1")))
        if x_xss_protection:
            self.headers.append((b"x-xss-protection", x_xss_protection.encode("latin-1")))
        if referrer_policy:
            self.headers.append((b"referrer-policy", referrer_policy.encode("latin-1")))
        if hsts_max_age is not None:
            hsts_val = f"max-age={hsts_max_age}"
            if hsts_include_subdomains:
                hsts_val += "; includeSubDomains"
            self.headers.append((b"strict-transport-security", hsts_val.encode("latin-1")))

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        """Process ASGI request/response."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Overwrite or append our security headers securely
                existing_keys = {k.lower() for k, _ in headers}
                for key, val in self.headers:
                    if key not in existing_keys:
                        headers.append((key, val))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)

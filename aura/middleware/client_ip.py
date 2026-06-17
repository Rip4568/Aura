"""Client IP resolution utilities for rate limiting and logging."""

from __future__ import annotations

from typing import Any, cast


def resolve_client_ip(
    client_host: str | None,
    forwarded_for: str | None,
    trusted_proxies: frozenset[str] | None,
) -> str:
    """Resolve the effective client IP for rate limiting.

    ``X-Forwarded-For`` is honoured only when the direct connection comes from
    a host listed in *trusted_proxies*.
    """
    if client_host:
        if (
            trusted_proxies
            and client_host in trusted_proxies
            and forwarded_for
        ):
            return forwarded_for.split(",")[0].strip()
        return client_host
    if forwarded_for and not trusted_proxies:
        return forwarded_for.split(",")[0].strip()
    return "unknown"


def client_ip_from_scope(
    scope: dict[str, Any],
    trusted_proxies: frozenset[str] | None = None,
) -> str:
    """Extract the rate-limit client IP from an ASGI scope."""
    client = scope.get("client")
    client_host = cast(str, client[0]) if client else None
    forwarded_for = _header_value(scope.get("headers", []), b"x-forwarded-for")
    return resolve_client_ip(client_host, forwarded_for, trusted_proxies)


def _header_value(
    headers: list[tuple[bytes, bytes]],
    name: bytes,
) -> str | None:
    for header_name, value in headers:
        if header_name.lower() == name:
            return value.decode()
    return None

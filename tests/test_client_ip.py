"""Tests for client IP resolution used by rate limiting."""

from __future__ import annotations

from aura.middleware.client_ip import client_ip_from_scope, resolve_client_ip


class TestResolveClientIp:
    def test_direct_client_without_proxy(self) -> None:
        assert resolve_client_ip("10.0.0.5", "1.2.3.4", frozenset({"10.0.0.1"})) == "10.0.0.5"

    def test_trusted_proxy_uses_xff(self) -> None:
        assert (
            resolve_client_ip(
                "10.0.0.1",
                "203.0.113.7, 10.0.0.1",
                frozenset({"10.0.0.1"}),
            )
            == "203.0.113.7"
        )

    def test_untrusted_proxy_ignores_xff(self) -> None:
        assert resolve_client_ip("10.0.0.9", "203.0.113.7", frozenset({"10.0.0.1"})) == "10.0.0.9"

    def test_scope_helper(self) -> None:
        scope = {
            "client": ("127.0.0.1", 12345),
            "headers": [(b"x-forwarded-for", b"198.51.100.4")],
        }
        assert client_ip_from_scope(scope, frozenset({"127.0.0.1"})) == "198.51.100.4"

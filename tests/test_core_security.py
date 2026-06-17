"""Tests for core security helpers."""

from __future__ import annotations

import pytest

from aura.core.app import _safe_config_dump
from aura.core.response import redirect
from aura.exceptions.http import BadRequestException


def test_redirect_allows_relative_path() -> None:
    response = redirect("/admin/login")
    assert response.status_code == 307
    assert response.headers["location"] == "/admin/login"


def test_redirect_blocks_absolute_url() -> None:
    with pytest.raises(BadRequestException):
        redirect("https://evil.example/phish")


def test_redirect_blocks_protocol_relative_url() -> None:
    with pytest.raises(BadRequestException):
        redirect("//evil.example/phish")


def test_safe_config_dump_redacts_secrets() -> None:
    from aura.config.base import AuraConfig

    cfg = AuraConfig(
        secret_key="super-secret-key-32chars-minimum!!",
    )
    cfg.database.url = "postgresql+asyncpg://user:pass@localhost/db"
    dumped = _safe_config_dump(cfg)
    assert dumped["secret_key"] == "***"
    assert dumped["database"]["url"] == "***"

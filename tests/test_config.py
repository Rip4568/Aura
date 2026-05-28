"""Tests for aura.config module."""

from __future__ import annotations

import os

import pytest

from aura.config.base import AuraConfig, DatabaseConfig, JobsConfig, ServerConfig
from aura.config.loader import get_env, load_config

# ---------------------------------------------------------------------------
# ServerConfig
# ---------------------------------------------------------------------------


def test_server_config_defaults() -> None:
    cfg = ServerConfig()
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 8000
    assert cfg.workers == 1
    assert cfg.reload is False


# ---------------------------------------------------------------------------
# DatabaseConfig
# ---------------------------------------------------------------------------


def test_database_config_defaults() -> None:
    cfg = DatabaseConfig()
    assert "sqlite" in cfg.url
    assert cfg.pool_size == 5
    assert cfg.echo is False


# ---------------------------------------------------------------------------
# JobsConfig
# ---------------------------------------------------------------------------


def test_jobs_config_defaults() -> None:
    cfg = JobsConfig()
    assert cfg.backend == "memory"
    assert cfg.default_queue == "default"
    assert cfg.max_workers == 4


# ---------------------------------------------------------------------------
# AuraConfig
# ---------------------------------------------------------------------------


def test_aura_config_defaults() -> None:
    cfg = AuraConfig()
    assert cfg.app_name == "Aura App"
    assert cfg.debug is False
    assert len(cfg.secret_key) >= 32


def test_aura_config_has_nested_configs() -> None:
    cfg = AuraConfig()
    assert isinstance(cfg.server, ServerConfig)
    assert isinstance(cfg.database, DatabaseConfig)
    assert isinstance(cfg.jobs, JobsConfig)


def test_aura_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "TestApp")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)

    cfg = AuraConfig()
    assert cfg.app_name == "TestApp"
    assert cfg.debug is True
    assert cfg.secret_key == "a" * 32


# ---------------------------------------------------------------------------
# load_config helper
# ---------------------------------------------------------------------------


def test_load_config_returns_default() -> None:
    cfg = load_config()
    assert isinstance(cfg, AuraConfig)


def test_load_config_custom_class() -> None:
    class MyConfig(AuraConfig):
        extra_setting: str = "hello"

    cfg = load_config(config_class=MyConfig)
    assert isinstance(cfg, MyConfig)
    assert cfg.extra_setting == "hello"


# ---------------------------------------------------------------------------
# get_env helper
# ---------------------------------------------------------------------------


def test_get_env_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_VAR", "my_value")
    assert get_env("MY_VAR") == "my_value"


def test_get_env_returns_default_when_missing() -> None:
    os.environ.pop("MISSING_VAR_XYZ", None)
    assert get_env("MISSING_VAR_XYZ", "default") == "default"

"""Tests for Aura lifecycle features:

1. DatabaseManager auto-init from AURA__DATABASE__URL
2. AuraTemplateModule.on_startup auto-called via ModuleRegistry
3. url_for() global registered in the Jinja2 template engine
"""

from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from aura import Aura
from aura.orm.session import DatabaseManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(**kwargs: Any) -> Aura:
    return Aura(title="Lifecycle Test", **kwargs)


# ---------------------------------------------------------------------------
# 1. DatabaseManager auto-init
# ---------------------------------------------------------------------------


def test_db_auto_init_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """AURA__DATABASE__URL in env → db singleton is initialised on startup."""
    monkeypatch.setenv("AURA__DATABASE__URL", "sqlite+aiosqlite:///:memory:")

    # Ensure the global singleton starts uninitialised for this test
    from aura.orm.session import db

    original_engine = db._engine
    original_factory = db._session_factory
    db._engine = None
    db._session_factory = None

    try:
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200

        assert db._engine is not None, "db._engine should be set after startup"
    finally:
        # Cleanup: restore previous state (close new engine synchronously via sync run)
        if db._engine is not None and db._engine is not original_engine:
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(db._engine.dispose())
            finally:
                loop.close()
        db._engine = original_engine
        db._session_factory = original_factory


def test_db_not_initialized_without_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without any database configuration the global db singleton stays untouched."""
    monkeypatch.delenv("AURA__DATABASE__URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "AURA__DATABASE__URL", ""
    )  # Makes cfg.database.url empty via pydantic-settings

    from aura.orm.session import db

    original_engine = db._engine

    # A fresh manager is always uninitialised
    fresh_manager = DatabaseManager()
    assert fresh_manager._engine is None

    app = _make_app()
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200

    # The fresh manager was never touched
    assert fresh_manager._engine is None
    # The global singleton should not have been changed
    assert db._engine is original_engine


# ---------------------------------------------------------------------------
# 2. Module on_startup auto-called
# ---------------------------------------------------------------------------


def test_template_module_on_startup_auto_called() -> None:
    """A module with an async on_startup staticmethod is called during app startup."""
    called: list[tuple[Any, bool]] = []

    class _FakeModule:
        __aura_module__ = type(
            "ModuleMetadata",
            (),
            {
                "imports": [],
                "providers": [],
                "controllers": [],
                "exports": [],
                "prefix": "",
                "tags": [],
                "guards": [],
            },
        )()

        @staticmethod
        async def on_startup(container: Any, debug: bool = False) -> None:
            called.append((container, debug))

    app = _make_app(modules=[_FakeModule])

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200

    assert len(called) == 1, "on_startup should have been called exactly once"
    container_arg, debug_arg = called[0]
    assert container_arg is app.container
    assert debug_arg is False


def test_sync_on_startup_also_called() -> None:
    """A module with a *synchronous* on_startup staticmethod is also invoked."""
    called: list[bool] = []

    class _SyncModule:
        __aura_module__ = type(
            "ModuleMetadata",
            (),
            {
                "imports": [],
                "providers": [],
                "controllers": [],
                "exports": [],
                "prefix": "",
                "tags": [],
                "guards": [],
            },
        )()

        @staticmethod
        def on_startup(container: Any, debug: bool = False) -> None:
            called.append(True)

    app = _make_app(modules=[_SyncModule])

    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200

    assert len(called) == 1


# ---------------------------------------------------------------------------
# 3. url_for() in templates
# ---------------------------------------------------------------------------


def test_url_for_in_templates() -> None:
    """AuraTemplateEngine.register_routes registers url_for that resolves names."""
    from aura.templates.engine import AuraTemplateEngine

    engine = AuraTemplateEngine(template_dirs=["templates"])

    # Build a minimal fake route list
    class _FakeRoute:
        def __init__(self, name: str, path: str) -> None:
            self.name = name
            self.path = path

    routes = [
        _FakeRoute("health", "/health"),
        _FakeRoute("get_user", "/users/{user_id}"),
        _FakeRoute("swagger_ui", "/docs"),
    ]

    engine.register_routes(routes)

    # url_for should now be a Jinja2 global
    assert "url_for" in engine._env.globals

    url_fn = engine._env.globals["url_for"]

    assert url_fn("health") == "/health"
    assert url_fn("swagger_ui") == "/docs"
    assert url_fn("get_user", user_id=42) == "/users/42"


def test_url_for_raises_for_unknown_route() -> None:
    """url_for raises RuntimeError for unknown route names."""
    from aura.templates.engine import AuraTemplateEngine

    engine = AuraTemplateEngine(template_dirs=["templates"])

    class _FakeRoute:
        def __init__(self, name: str, path: str) -> None:
            self.name = name
            self.path = path

    engine.register_routes([_FakeRoute("health", "/health")])
    url_fn = engine._env.globals["url_for"]

    with pytest.raises(RuntimeError, match="no route named"):
        url_fn("does_not_exist")


def test_url_for_registered_after_app_startup() -> None:
    """After app startup the template engine's url_for can resolve 'health'."""
    import aura.templates.shortcuts as _shortcuts
    from aura.templates.engine import AuraTemplateEngine
    from aura.templates.shortcuts import set_engine

    engine = AuraTemplateEngine(template_dirs=["templates"])
    previous_engine = _shortcuts._engine
    set_engine(engine)

    try:
        app = _make_app()
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200

        url_fn = engine._env.globals.get("url_for")
        assert url_fn is not None, "url_for global should be registered"
        assert url_fn("health") == "/health"
    finally:
        set_engine(previous_engine)

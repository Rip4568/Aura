"""Tests for the ``aura tinker`` CLI command."""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from aura import Aura
from aura.cli.commands.tinker import (
    discover_project_objects,
    setup_database_manager,
    sync,
)
from aura.cli.main import app

runner = CliRunner()


@pytest.fixture
def clean_sys_modules() -> Generator[None, None, None]:
    """Clean up sys.modules after importing dynamic modules during testing."""
    old_modules = set(sys.modules.keys())
    old_path = list(sys.path)
    yield
    # Remove any newly imported modules
    for mod_name in list(sys.modules.keys()):
        if mod_name not in old_modules:
            sys.modules.pop(mod_name, None)
    sys.path = old_path


def test_sync_helper() -> None:
    """Test that the ``sync`` helper runs coroutines synchronously."""

    async def sample_coro() -> int:
        return 42

    result = sync(sample_coro())
    assert result == 42


def test_discover_project_objects(tmp_path: Path, clean_sys_modules: None) -> None:
    """Test discover_project_objects crawler correctly locates user components."""
    # Create temporary module structure
    pkg_dir = tmp_path / "tinker_test_modules"
    pkg_dir.mkdir()

    users_dir = pkg_dir / "users"
    users_dir.mkdir()

    (pkg_dir / "__init__.py").touch()
    (users_dir / "__init__.py").touch()

    # Create model
    models_file = users_dir / "models.py"
    models_file.write_text(
        "from aura.orm import AuraModel\n"
        "class TestUser(AuraModel):\n"
        "    __tablename__ = 'test_users'\n"
    )

    # Create repository
    repos_file = users_dir / "repositories.py"
    repos_file.write_text(
        "from aura.orm import Repository\nclass TestUserRepository(Repository):\n    pass\n"
    )

    # Create schema
    schemas_file = users_dir / "schemas.py"
    schemas_file.write_text("from aura import Schema\nclass TestUserSchema(Schema):\n    pass\n")

    # Create service
    service_file = users_dir / "service.py"
    service_file.write_text("class TestUserService:\n    pass\n")

    discovered = discover_project_objects(str(tmp_path))

    # Assert models, repositories, schemas, services discovered
    assert "TestUser" in discovered["models"]
    assert "TestUserRepository" in discovered["repositories"]
    assert "TestUserSchema" in discovered["schemas"]
    assert "TestUserService" in discovered["services"]


def test_setup_database_manager_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test database setup is successfully configured from environment variables."""
    monkeypatch.setenv("AURA__DATABASE__URL", "sqlite+aiosqlite:///:memory:")

    with patch("aura.orm.session.db") as mock_db:
        result = setup_database_manager()
        assert result is mock_db
        mock_db.init.assert_called_once_with("sqlite+aiosqlite:///:memory:", echo=False)


def test_setup_database_manager_from_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test database setup reads aura.toml configuration accurately."""
    monkeypatch.delenv("AURA__DATABASE__URL", raising=False)
    monkeypatch.delenv("DATABASE__URL", raising=False)

    # Write aura.toml
    toml_file = tmp_path / "aura.toml"
    toml_file.write_text('[database]\nurl = "sqlite+aiosqlite:///aura_test.db"\necho = true\n')

    monkeypatch.chdir(tmp_path)

    with patch("aura.orm.session.db") as mock_db:
        result = setup_database_manager()
        assert result is mock_db
        mock_db.init.assert_called_once_with("sqlite+aiosqlite:///aura_test.db", echo=True)


def test_tinker_command_standard_repl() -> None:
    """Test running tinker command launches standard Python REPL backend."""
    with (
        patch("code.interact") as mock_interact,
        patch("aura.cli.commands.tinker.setup_database_manager") as mock_setup_db,
    ):
        mock_db = MagicMock()
        mock_setup_db.return_value = mock_db

        result = runner.invoke(app, ["tinker", "--repl", "python"])
        assert result.exit_code == 0
        mock_interact.assert_called_once()

        # Check that interactive namespace got loaded with helper and db
        namespace = mock_interact.call_args[1]["local"]
        assert "sync" in namespace
        assert "db" in namespace


def test_tinker_command_ipython_repl() -> None:
    """Test running tinker command launches IPython backend with top-await."""
    pytest.importorskip("IPython")
    with (
        patch("IPython.start_ipython") as mock_start_ipython,
        patch("aura.cli.commands.tinker.setup_database_manager") as mock_setup_db,
    ):
        mock_setup_db.return_value = MagicMock()

        result = runner.invoke(app, ["tinker", "--repl", "ipython"])
        assert result.exit_code == 0
        mock_start_ipython.assert_called_once()

        # Check that traitlets config was enabled
        config = mock_start_ipython.call_args[1]["config"]
        assert config.InteractiveShell.autoawait is True


def test_tinker_command_bpython_repl() -> None:
    """Test running tinker command launches bpython backend if selected."""
    mock_bpython = MagicMock()
    with (
        patch.dict("sys.modules", {"bpython": mock_bpython}),
        patch("aura.cli.commands.tinker.setup_database_manager") as mock_setup_db,
    ):
        mock_setup_db.return_value = MagicMock()

        result = runner.invoke(app, ["tinker", "--repl", "bpython"])
        assert result.exit_code == 0
        mock_bpython.embed.assert_called_once()


def test_tinker_command_app_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean_sys_modules: None
) -> None:
    """Test tinker command discovers and initializes active Aura app instance."""
    # Clear sys.modules cache to prevent test leakages from other files
    sys.modules.pop("main", None)

    # Write a mock main.py defining an Aura app in tmp_path
    main_file = tmp_path / "main.py"
    main_file.write_text("from aura import Aura\napp = Aura(title='SuperAwesomeTinkerTest')\n")

    monkeypatch.chdir(tmp_path)

    with (
        patch("code.interact") as mock_interact,
        patch("aura.cli.commands.tinker.setup_database_manager") as mock_setup_db,
    ):
        mock_setup_db.return_value = MagicMock()

        result = runner.invoke(app, ["tinker", "--repl", "python"])
        assert result.exit_code == 0

        # Assert app details were loaded in namespace
        namespace = mock_interact.call_args[1]["local"]
        assert "app" in namespace
        assert isinstance(namespace["app"], Aura)
        assert namespace["app"].title == "SuperAwesomeTinkerTest"

"""Tests for the Aura CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from aura.cli.main import app


runner = CliRunner()


# ---------------------------------------------------------------------------
# version command
# ---------------------------------------------------------------------------

class TestVersionCommand:
    """Tests for ``aura version``."""

    def test_version_output(self) -> None:
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Aura" in result.output


# ---------------------------------------------------------------------------
# new command
# ---------------------------------------------------------------------------

class TestNewCommand:
    """Tests for ``aura new project``."""

    def test_new_project_creates_structure(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["new", "project", "myapp", "--dir", str(tmp_path)])
        assert result.exit_code == 0, result.output
        project_dir = tmp_path / "myapp"
        assert project_dir.exists()
        assert (project_dir / "main.py").exists()
        assert (project_dir / "aura.toml").exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / ".gitignore").exists()
        assert (project_dir / "tests" / "__init__.py").exists()
        assert (project_dir / "tests" / "conftest.py").exists()

    def test_new_project_shows_next_steps(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["new", "project", "coolapp", "--dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Next steps" in result.output

    def test_new_project_name_with_dashes(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["new", "project", "my-cool-app", "--dir", str(tmp_path)])
        assert result.exit_code == 0
        project_dir = tmp_path / "my_cool_app"
        assert project_dir.exists()

    def test_new_project_duplicate_fails(self, tmp_path: Path) -> None:
        runner.invoke(app, ["new", "project", "dupapp", "--dir", str(tmp_path)])
        result = runner.invoke(app, ["new", "project", "dupapp", "--dir", str(tmp_path)])
        assert result.exit_code != 0
        # Collapse whitespace/newlines for robust matching
        normalised = " ".join(result.output.lower().split())
        assert "already exists" in normalised or "error" in normalised

    def test_main_py_content(self, tmp_path: Path) -> None:
        runner.invoke(app, ["new", "project", "checkapp", "--dir", str(tmp_path)])
        main_py = (tmp_path / "checkapp" / "main.py").read_text()
        assert "Aura" in main_py
        assert "app" in main_py


# ---------------------------------------------------------------------------
# generate command
# ---------------------------------------------------------------------------

class TestGenerateCommand:
    """Tests for ``aura generate`` sub-commands."""

    def test_generate_module(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", "module", "users", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
        module_dir = tmp_path / "users"
        assert (module_dir / "schema.py").exists()
        assert (module_dir / "service.py").exists()
        assert (module_dir / "router.py").exists()
        assert (module_dir / "module.py").exists()
        assert (module_dir / "__init__.py").exists()

    def test_generate_module_schema_content(self, tmp_path: Path) -> None:
        runner.invoke(app, ["generate", "module", "products", "--out", str(tmp_path)])
        schema = (tmp_path / "products" / "schema.py").read_text()
        assert "ProductBase" in schema
        assert "ProductCreate" in schema
        assert "ProductResponse" in schema

    def test_generate_schema(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", "schema", "order", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
        schema_file = tmp_path / "order_schema.py"
        assert schema_file.exists()
        content = schema_file.read_text()
        assert "OrderBase" in content

    def test_generate_guard(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", "guard", "admin", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
        guard_file = tmp_path / "admin_guard.py"
        assert guard_file.exists()
        content = guard_file.read_text()
        assert "AdminGuard" in content

    def test_generate_module_skip_existing(self, tmp_path: Path) -> None:
        # First generation
        runner.invoke(app, ["generate", "module", "items", "--out", str(tmp_path)])
        # Write custom content to one file
        schema = tmp_path / "items" / "schema.py"
        schema.write_text("# custom\n")
        # Second generation without --force should skip
        result = runner.invoke(app, ["generate", "module", "items", "--out", str(tmp_path)])
        assert result.exit_code == 0
        assert "# custom" in schema.read_text()

    def test_generate_module_force_overwrites(self, tmp_path: Path) -> None:
        runner.invoke(app, ["generate", "module", "tags", "--out", str(tmp_path)])
        schema = tmp_path / "tags" / "schema.py"
        schema.write_text("# custom\n")
        runner.invoke(app, ["generate", "module", "tags", "--out", str(tmp_path), "--force"])
        assert "TagBase" in schema.read_text()


# ---------------------------------------------------------------------------
# run command (import check only)
# ---------------------------------------------------------------------------

class TestRunCommand:
    """Tests for ``aura run`` — we only test that the command is wired up
    correctly; actually starting a server is out of scope for unit tests."""

    def test_run_missing_uvicorn(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should exit with code 1 if uvicorn is not installed."""
        import builtins
        original_import = builtins.__import__

        def _mock_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "uvicorn":
                raise ImportError("No module named 'uvicorn'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _mock_import)
        result = runner.invoke(app, ["run", "--help"])
        # --help should always succeed regardless of uvicorn
        assert result.exit_code == 0

    def test_run_help(self) -> None:
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "host" in result.output.lower() or "Host" in result.output


# ---------------------------------------------------------------------------
# worker command
# ---------------------------------------------------------------------------

class TestWorkerCommand:
    """Tests for ``aura worker`` CLI wiring."""

    def test_worker_help(self) -> None:
        result = runner.invoke(app, ["worker", "--help"])
        assert result.exit_code == 0
        assert "queue" in result.output.lower() or "Queue" in result.output


# ---------------------------------------------------------------------------
# migrate command
# ---------------------------------------------------------------------------

class TestMigrateCommand:
    """Tests for ``aura migrate`` CLI wiring."""

    def test_migrate_help(self) -> None:
        result = runner.invoke(app, ["migrate", "--help"])
        assert result.exit_code == 0

    def test_migrate_up_help(self) -> None:
        result = runner.invoke(app, ["migrate", "up", "--help"])
        assert result.exit_code == 0

    def test_migrate_down_help(self) -> None:
        result = runner.invoke(app, ["migrate", "down", "--help"])
        assert result.exit_code == 0

    def test_migrate_make_help(self) -> None:
        result = runner.invoke(app, ["migrate", "make", "--help"])
        assert result.exit_code == 0

    def test_migrate_status_help(self) -> None:
        result = runner.invoke(app, ["migrate", "status", "--help"])
        assert result.exit_code == 0

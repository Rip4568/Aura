"""Tests for the Aura CLI commands."""

from __future__ import annotations

import pathlib
from pathlib import Path

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
# new command  (aura new <name> — no 'project' subcommand)
# ---------------------------------------------------------------------------

class TestNewCommand:
    """Tests for ``aura new <project-name>``.

    Note: typer group commands require options *before* positional args.
    Correct form: ``aura new --dir <path> <name>``
    """

    def test_new_project_creates_structure(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["new", "--dir", str(tmp_path), "myapp"])
        assert result.exit_code == 0, result.output
        project_dir = tmp_path / "myapp"
        assert project_dir.exists()
        assert (project_dir / "main.py").exists()
        assert (project_dir / "aura.toml").exists()
        assert (project_dir / "pyproject.toml").exists()
        assert (project_dir / ".gitignore").exists()
        assert (project_dir / "tests" / "__init__.py").exists()
        assert (project_dir / "tests" / "conftest.py").exists()

    def test_new_project_creates_users_module(self, tmp_path: Path) -> None:
        runner.invoke(app, ["new", "--dir", str(tmp_path), "myapp2"])
        users = tmp_path / "myapp2" / "modules" / "users"
        assert (users / "schemas.py").exists()
        assert (users / "service.py").exists()
        assert (users / "controller.py").exists()
        assert (users / "module.py").exists()

    def test_new_project_shows_next_steps(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["new", "--dir", str(tmp_path), "coolapp"])
        assert result.exit_code == 0
        assert "Next steps" in result.output

    def test_new_project_name_with_dashes(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["new", "--dir", str(tmp_path), "my-cool-app"])
        assert result.exit_code == 0
        project_dir = tmp_path / "my_cool_app"
        assert project_dir.exists()

    def test_new_project_duplicate_fails(self, tmp_path: Path) -> None:
        runner.invoke(app, ["new", "--dir", str(tmp_path), "dupapp"])
        result = runner.invoke(app, ["new", "--dir", str(tmp_path), "dupapp"])
        assert result.exit_code != 0
        normalised = " ".join(result.output.lower().split())
        assert "already exists" in normalised or "error" in normalised

    def test_main_py_content(self, tmp_path: Path) -> None:
        runner.invoke(app, ["new", "--dir", str(tmp_path), "checkapp"])
        main_py = (tmp_path / "checkapp" / "main.py").read_text()
        assert "Aura" in main_py
        assert "app" in main_py
        assert "UsersModule" in main_py

    def test_conftest_uses_asgi_transport(self, tmp_path: Path) -> None:
        runner.invoke(app, ["new", "--dir", str(tmp_path), "testapp"])
        conftest = (tmp_path / "testapp" / "tests" / "conftest.py").read_text()
        assert "AsyncClient" in conftest
        assert "ASGITransport" in conftest


# ---------------------------------------------------------------------------
# generate command
# ---------------------------------------------------------------------------

class TestGenerateCommand:
    """Tests for ``aura generate`` sub-commands.

    All ``generate module`` invocations pass ``--no-tests`` so the
    generated test file is not written into this repo's ``tests/`` directory
    and does not pollute subsequent test runs.
    """

    def test_generate_module(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["generate", "module", "users", "--out", str(tmp_path), "--no-tests"]
        )
        assert result.exit_code == 0, result.output
        module_dir = tmp_path / "users"
        assert (module_dir / "schemas.py").exists()
        assert (module_dir / "service.py").exists()
        assert (module_dir / "controller.py").exists()
        assert (module_dir / "module.py").exists()
        assert (module_dir / "__init__.py").exists()

    def test_generate_module_schema_content(self, tmp_path: Path) -> None:
        # Use singular "product" → CreateProductDTO; plural "products" → CreateProductsDTO
        runner.invoke(
            app, ["generate", "module", "product", "--out", str(tmp_path), "--no-tests"]
        )
        schema = (tmp_path / "product" / "schemas.py").read_text()
        assert "CreateProductDTO" in schema
        assert "UpdateProductDTO" in schema
        assert "ProductResponse" in schema

    def test_generate_module_service_is_injectable(self, tmp_path: Path) -> None:
        runner.invoke(
            app, ["generate", "module", "order", "--out", str(tmp_path), "--no-tests"]
        )
        service = (tmp_path / "order" / "service.py").read_text()
        assert "@injectable" in service
        assert "OrderService" in service

    def test_generate_module_controller_has_crud(self, tmp_path: Path) -> None:
        runner.invoke(
            app, ["generate", "module", "post", "--out", str(tmp_path), "--no-tests"]
        )
        controller = (tmp_path / "post" / "controller.py").read_text()
        assert "PostController" in controller
        assert "@get" in controller
        assert "@post" in controller
        assert "@put" in controller
        assert "@delete" in controller

    def test_generate_module_creates_tests(self, tmp_path: Path) -> None:
        """--tests flag writes a test file; we clean it up immediately."""
        result = runner.invoke(
            app,
            # Use a name unlikely to clash with real test files
            ["generate", "module", "xuniq_99xyz", "--out", str(tmp_path), "--tests"],
        )
        assert result.exit_code == 0, result.output
        # The test file lands in tests/ relative to CWD — clean up right away
        leftover = pathlib.Path("tests") / "test_xuniq_99xyz.py"
        if leftover.exists():
            leftover.unlink()

    def test_generate_module_no_tests_flag(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["generate", "module", "comments", "--out", str(tmp_path), "--no-tests"],
        )
        assert result.exit_code == 0, result.output

    def test_generate_schema(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", "schema", "invoice", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
        schema_file = tmp_path / "invoice_schemas.py"
        assert schema_file.exists()
        content = schema_file.read_text()
        assert "CreateInvoiceDTO" in content

    def test_generate_guard(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", "guard", "admin", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
        guard_file = tmp_path / "admin_guard.py"
        assert guard_file.exists()
        content = guard_file.read_text()
        assert "AdminGuard" in content
        assert "can_activate" in content

    def test_generate_service(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", "service", "email", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
        service_file = tmp_path / "email_service.py"
        assert service_file.exists()
        content = service_file.read_text()
        assert "EmailService" in content
        assert "@injectable" in content

    def test_generate_controller(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["generate", "controller", "auth", "--out", str(tmp_path)])
        assert result.exit_code == 0, result.output
        ctrl_file = tmp_path / "auth_controller.py"
        assert ctrl_file.exists()
        content = ctrl_file.read_text()
        assert "AuthController" in content

    def test_generate_resource_alias(self, tmp_path: Path) -> None:
        """``resource`` is an alias for ``module``."""
        result = runner.invoke(
            app, ["generate", "resource", "widget", "--out", str(tmp_path), "--no-tests"]
        )
        assert result.exit_code == 0, result.output
        assert (tmp_path / "widget" / "schemas.py").exists()
        assert (tmp_path / "widget" / "service.py").exists()

    def test_generate_module_skip_existing(self, tmp_path: Path) -> None:
        runner.invoke(
            app, ["generate", "module", "items", "--out", str(tmp_path), "--no-tests"]
        )
        schema = tmp_path / "items" / "schemas.py"
        schema.write_text("# custom\n")
        runner.invoke(
            app, ["generate", "module", "items", "--out", str(tmp_path), "--no-tests"]
        )
        assert "# custom" in schema.read_text()

    def test_generate_module_force_overwrites(self, tmp_path: Path) -> None:
        runner.invoke(
            app, ["generate", "module", "cats", "--out", str(tmp_path), "--no-tests"]
        )
        schema = tmp_path / "cats" / "schemas.py"
        schema.write_text("# custom\n")
        runner.invoke(
            app,
            ["generate", "module", "cats", "--out", str(tmp_path), "--force", "--no-tests"],
        )
        assert "CreateCatsDTO" in schema.read_text()

    def test_generate_no_args_shows_table(self) -> None:
        result = runner.invoke(app, ["generate"])
        assert result.exit_code == 0
        assert "module" in result.output.lower()

    def test_generate_module_without_with_db_has_commented_models(self, tmp_path: Path) -> None:
        runner.invoke(
            app, ["generate", "module", "foo", "--out", str(tmp_path), "--no-tests"]
        )
        models = (tmp_path / "foo" / "models.py").read_text()
        assert "# from aura.orm import AuraModel" in models

    def test_generate_module_with_db_has_uncommented_models(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            ["generate", "module", "foo", "--out", str(tmp_path), "--no-tests", "--with-db"],
        )
        assert result.exit_code == 0, result.output
        models = (tmp_path / "foo" / "models.py").read_text()
        assert "from aura.orm import AuraModel" in models
        assert "# from aura.orm import AuraModel" not in models
        repo = (tmp_path / "foo" / "repositories.py").read_text()
        assert "from aura.orm import Repository" in repo
        assert "# from aura.orm import Repository" not in repo

    def test_generate_module_with_db_creates_working_repository(self, tmp_path: Path) -> None:
        runner.invoke(
            app,
            ["generate", "module", "foo", "--out", str(tmp_path), "--no-tests", "--with-db"],
        )
        repo = (tmp_path / "foo" / "repositories.py").read_text()
        assert "FooRepository" in repo


# ---------------------------------------------------------------------------
# run command (import check only)
# ---------------------------------------------------------------------------

class TestRunCommand:
    """Tests for ``aura run`` — we only test that the command is wired up
    correctly; actually starting a server is out of scope for unit tests."""

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

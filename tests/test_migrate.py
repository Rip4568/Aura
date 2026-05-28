"""Tests for ``aura migrate`` CLI commands and migration helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from aura.cli.commands.migrate import _generate_alembic_ini, app
from aura.orm.migrations import generate_env_py

runner = CliRunner()

# ---------------------------------------------------------------------------
# make
# ---------------------------------------------------------------------------


class TestMakeCommand:
    """Tests for ``aura migrate make``."""

    def test_make_with_message(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["make", "add users table"])
            assert result.exit_code == 0
            called_args: list[str] = mock_run.call_args[0][0]
            assert "revision" in called_args
            assert "--message" in called_args
            assert "add users table" in called_args

    def test_make_without_message_uses_timestamp(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["make"])
            assert result.exit_code == 0
            called_args: list[str] = mock_run.call_args[0][0]
            assert "--message" in called_args
            msg_idx = called_args.index("--message")
            msg = called_args[msg_idx + 1]
            # timestamp format: YYYYMMDD_HHMMSS — 15 chars, all digits except underscore
            assert len(msg) == 15
            assert msg.replace("_", "").isdigit()

    def test_make_autogenerate_flag_present_by_default(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(app, ["make", "test"])
            called_args: list[str] = mock_run.call_args[0][0]
            assert "--autogenerate" in called_args

    def test_make_no_autogenerate(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(app, ["make", "test", "--no-autogenerate"])
            called_args: list[str] = mock_run.call_args[0][0]
            assert "--autogenerate" not in called_args

    def test_make_failure_exits_with_nonzero(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = runner.invoke(app, ["make", "test"])
            assert result.exit_code == 1


# ---------------------------------------------------------------------------
# up
# ---------------------------------------------------------------------------


class TestUpCommand:
    """Tests for ``aura migrate up``."""

    def test_up_default_to_head(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["up"])
            assert result.exit_code == 0
            assert "head" in mock_run.call_args[0][0]

    def test_up_specific_revision(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["up", "abc123"])
            assert result.exit_code == 0
            assert "abc123" in mock_run.call_args[0][0]

    def test_up_invokes_upgrade_subcommand(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(app, ["up"])
            called_args: list[str] = mock_run.call_args[0][0]
            assert "upgrade" in called_args

    def test_up_failure_exits_with_code(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = runner.invoke(app, ["up"])
            assert result.exit_code == 1


# ---------------------------------------------------------------------------
# down
# ---------------------------------------------------------------------------


class TestDownCommand:
    """Tests for ``aura migrate down``."""

    def test_down_default(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["down"])
            assert result.exit_code == 0
            assert "-1" in mock_run.call_args[0][0]

    def test_down_specific_revision(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["down", "base"])
            assert result.exit_code == 0
            assert "base" in mock_run.call_args[0][0]

    def test_down_invokes_downgrade_subcommand(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(app, ["down"])
            called_args: list[str] = mock_run.call_args[0][0]
            assert "downgrade" in called_args

    def test_down_failure_exits_with_code(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = runner.invoke(app, ["down"])
            assert result.exit_code == 1


# ---------------------------------------------------------------------------
# stamp
# ---------------------------------------------------------------------------


class TestStampCommand:
    """Tests for ``aura migrate stamp``."""

    def test_stamp_head(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["stamp", "head"])
            assert result.exit_code == 0
            called_args: list[str] = mock_run.call_args[0][0]
            assert "stamp" in called_args
            assert "head" in called_args

    def test_stamp_base(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["stamp", "base"])
            assert result.exit_code == 0
            assert "base" in mock_run.call_args[0][0]

    def test_stamp_default_is_head(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(app, ["stamp"])
            called_args: list[str] = mock_run.call_args[0][0]
            assert "head" in called_args

    def test_stamp_specific_revision(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["stamp", "abc123"])
            assert result.exit_code == 0
            assert "abc123" in mock_run.call_args[0][0]

    def test_stamp_failure_exits_with_code(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = runner.invoke(app, ["stamp", "head"])
            assert result.exit_code == 1


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


class TestStatusCommand:
    """Tests for ``aura migrate status``."""

    def test_status_runs_current_and_history(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            # Should have called alembic at least twice (current + history)
            assert mock_run.call_count >= 2

    def test_status_calls_current(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(app, ["status"])
            all_calls = [call[0][0] for call in mock_run.call_args_list]
            assert any("current" in args for args in all_calls)

    def test_status_calls_history(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            runner.invoke(app, ["status"])
            all_calls = [call[0][0] for call in mock_run.call_args_list]
            assert any("history" in args for args in all_calls)


# ---------------------------------------------------------------------------
# Alembic not installed
# ---------------------------------------------------------------------------


class TestAlembicNotInstalled:
    """Tests for behaviour when Alembic is not available."""

    def test_alembic_not_installed_shows_error(self) -> None:
        with patch.dict("sys.modules", {"alembic": None}):  # type: ignore[dict-item]
            result = runner.invoke(app, ["make", "test"])
            assert result.exit_code == 1
            output_lower = result.output.lower()
            assert "not installed" in output_lower or "pip install" in output_lower


# ---------------------------------------------------------------------------
# no-subcommand callback
# ---------------------------------------------------------------------------


class TestListCommandsCallback:
    """Tests for the command table shown when no sub-command is given."""

    def test_no_subcommand_shows_command_table(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "make" in result.output
        assert "up" in result.output
        assert "down" in result.output
        assert "stamp" in result.output
        assert "status" in result.output


# ---------------------------------------------------------------------------
# init command
# ---------------------------------------------------------------------------


class TestInitCommand:
    """Tests for ``aura migrate init``."""

    def test_init_creates_directory_structure(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # Change working directory via runner mix_stderr/env or use monkeypatch
            import os

            orig = os.getcwd()
            os.chdir(tmp_path)
            try:
                result = runner.invoke(app, ["init"])
                assert result.exit_code == 0
                assert (tmp_path / "migrations").is_dir()
                assert (tmp_path / "migrations" / "versions").is_dir()
                assert (tmp_path / "alembic.ini").exists()
                assert (tmp_path / "migrations" / "env.py").exists()
            finally:
                os.chdir(orig)

    def test_init_with_models_generates_import(self, tmp_path: Path) -> None:
        import os

        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["init", "--models", "myapp.models:Base"])
            assert result.exit_code == 0
            env_content = (tmp_path / "migrations" / "env.py").read_text()
            assert "from myapp.models import Base" in env_content
            assert "target_metadata = target_metadata_base.metadata" in env_content
        finally:
            os.chdir(orig)

    def test_init_without_models_generates_placeholder(self, tmp_path: Path) -> None:
        import os

        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(app, ["init"])
            assert result.exit_code == 0
            env_content = (tmp_path / "migrations" / "env.py").read_text()
            assert "AuraModel" in env_content
        finally:
            os.chdir(orig)

    def test_init_custom_url_written_to_ini(self, tmp_path: Path) -> None:
        import os

        orig = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = runner.invoke(
                app, ["init", "--url", "postgresql+asyncpg://localhost/mydb"]
            )
            assert result.exit_code == 0
            ini_content = (tmp_path / "alembic.ini").read_text()
            assert "postgresql+asyncpg://localhost/mydb" in ini_content
        finally:
            os.chdir(orig)


# ---------------------------------------------------------------------------
# _generate_alembic_ini helper
# ---------------------------------------------------------------------------


class TestGenerateAlembicIni:
    """Tests for the ``_generate_alembic_ini`` helper."""

    def test_contains_script_location(self) -> None:
        ini = _generate_alembic_ini("migrations", "sqlite+aiosqlite:///./dev.db")
        assert "script_location = migrations" in ini

    def test_contains_db_url(self) -> None:
        ini = _generate_alembic_ini("migrations", "sqlite+aiosqlite:///./dev.db")
        assert "sqlite+aiosqlite:///./dev.db" in ini

    def test_custom_migrations_dir(self) -> None:
        ini = _generate_alembic_ini("db/migrations", "sqlite:///./test.db")
        assert "script_location = db/migrations" in ini

    def test_has_alembic_section(self) -> None:
        ini = _generate_alembic_ini("migrations", "sqlite:///./dev.db")
        assert "[alembic]" in ini


# ---------------------------------------------------------------------------
# generate_env_py helper
# ---------------------------------------------------------------------------


class TestGenerateEnvPy:
    """Tests for ``aura.orm.migrations.generate_env_py``."""

    def test_with_model_import(self) -> None:
        content = generate_env_py(Path("migrations"), "myapp.models:Base")
        assert "from myapp.models import Base" in content
        assert "target_metadata = target_metadata_base.metadata" in content
        assert "run_migrations_offline" in content
        assert "run_migrations_online" in content

    def test_with_nested_module_import(self) -> None:
        content = generate_env_py(Path("migrations"), "myapp.db.models:AuraBase")
        assert "from myapp.db.models import AuraBase" in content

    def test_without_model_import_has_placeholder(self) -> None:
        content = generate_env_py(Path("migrations"), None)
        assert "AuraModel" in content
        assert "run_migrations_offline" in content
        assert "run_migrations_online" in content

    def test_without_model_import_no_broken_import(self) -> None:
        content = generate_env_py(Path("migrations"), None)
        # Should not have a real import statement for an undefined module
        assert "from None" not in content
        assert "import None" not in content

    def test_contains_alembic_context(self) -> None:
        content = generate_env_py(Path("migrations"), "app.models:Base")
        assert "from alembic import context" in content

    def test_contains_async_engine(self) -> None:
        content = generate_env_py(Path("migrations"), "app.models:Base")
        assert "create_async_engine" in content


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestResetCommand:
    """Tests for ``aura migrate reset``."""

    def test_reset_with_yes_flag_runs_down_then_up(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["reset", "--yes"])
            assert result.exit_code == 0
            calls = [c[0][0] for c in mock_run.call_args_list]
            # first call: downgrade base
            assert "downgrade" in calls[0]
            assert "base" in calls[0]
            # second call: upgrade head
            assert "upgrade" in calls[1]
            assert "head" in calls[1]

    def test_reset_short_yes_flag(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["reset", "-y"])
            assert result.exit_code == 0

    def test_reset_aborts_without_confirmation(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            # simulate user typing "n" at the prompt
            result = runner.invoke(app, ["reset"], input="n\n")
            assert result.exit_code != 0
            mock_run.assert_not_called()

    def test_reset_proceeds_with_confirmation(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["reset"], input="y\n")
            assert result.exit_code == 0
            assert mock_run.call_count == 2

    def test_reset_aborts_if_downgrade_fails(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            result = runner.invoke(app, ["reset", "--yes"])
            assert result.exit_code == 1
            # upgrade must NOT be called when downgrade fails
            assert mock_run.call_count == 1

    def test_reset_fails_if_upgrade_fails(self) -> None:
        with patch("subprocess.run") as mock_run:
            # first call (downgrade) succeeds, second (upgrade) fails
            mock_run.side_effect = [MagicMock(returncode=0), MagicMock(returncode=1)]
            result = runner.invoke(app, ["reset", "--yes"])
            assert result.exit_code == 1
            assert mock_run.call_count == 2

    def test_reset_shows_warning_panel(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = runner.invoke(app, ["reset", "--yes"])
            out = result.output.lower()
            assert "warning" in out or "destroy" in out

    def test_reset_listed_in_command_table(self) -> None:
        result = runner.invoke(app, [])
        assert "reset" in result.output

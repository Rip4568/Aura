"""``aura migrate`` commands — Alembic wrapper with improved UX."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Database migration commands (Alembic wrapper).")
console = Console()


def _run_alembic(*args: str, cwd: Path | None = None) -> int:
    """Run an Alembic sub-command and stream its output.

    Args:
        *args: Arguments to pass to ``alembic``.
        cwd: Working directory (defaults to current directory).

    Returns:
        The process return code.
    """
    try:
        import alembic  # noqa: F401 — ensure it's installed
    except ImportError:
        console.print(
            "[red]Alembic is not installed.[/] "
            "Run: [bold]pip install aura-framework[sqlalchemy][/]"
        )
        raise typer.Exit(1)

    cmd = [sys.executable, "-m", "alembic", *args]
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    return result.returncode


@app.command("make")
def make_migration(
    message: str = typer.Argument(..., help="Short description of the migration"),
    autogenerate: bool = typer.Option(
        True,
        "--autogenerate/--no-autogenerate",
        help="Auto-detect model changes",
    ),
    migrations_dir: str = typer.Option("migrations", "--dir", help="Alembic migrations directory"),
) -> None:
    """Create a new migration revision.

    Examples::

        aura migrate make "add users table"
        aura migrate make "add index on email" --no-autogenerate
    """
    console.print(f"[bold]Creating migration:[/] {message}")
    extra = ["--autogenerate"] if autogenerate else []
    code = _run_alembic("revision", *extra, "--message", message)
    if code != 0:
        raise typer.Exit(code)
    console.print("[green]Migration created.[/]")


@app.command("up")
def migrate_up(
    revision: str = typer.Argument("head", help="Target revision (default: head)"),
) -> None:
    """Apply pending migrations (upgrade).

    Examples::

        aura migrate up          # apply all pending
        aura migrate up +1       # apply one migration
        aura migrate up abc123   # apply up to specific revision
    """
    console.print(f"[bold]Applying migrations up to:[/] [cyan]{revision}[/]")
    code = _run_alembic("upgrade", revision)
    if code != 0:
        raise typer.Exit(code)
    console.print("[green]Migrations applied.[/]")


@app.command("down")
def migrate_down(
    revision: str = typer.Argument("-1", help="Target revision (default: -1 = one step back)"),
) -> None:
    """Revert migrations (downgrade).

    Examples::

        aura migrate down        # revert last migration
        aura migrate down -2     # revert last two
        aura migrate down base   # revert all
    """
    console.print(f"[bold]Reverting migrations to:[/] [cyan]{revision}[/]")
    code = _run_alembic("downgrade", revision)
    if code != 0:
        raise typer.Exit(code)
    console.print("[yellow]Migrations reverted.[/]")


@app.command("status")
def migrate_status() -> None:
    """Show the current migration state."""
    console.print("[bold]Current migration status:[/]\n")
    _run_alembic("current")
    console.print()
    console.print("[bold]Migration history:[/]\n")
    _run_alembic("history", "--verbose")


@app.command("init")
def migrate_init(
    migrations_dir: str = typer.Argument("migrations", help="Directory to create"),
    model_import: str = typer.Option(
        None,
        "--models",
        help="Import path for your AuraModel base, e.g. 'myapp.models:Base'",
    ),
) -> None:
    """Initialise a new Alembic migrations environment.

    Creates the ``migrations/`` directory with ``env.py`` and ``alembic.ini``.

    Examples::

        aura migrate init
        aura migrate init --models myapp.models:Base
    """
    console.print(f"[bold]Initialising Alembic in [cyan]{migrations_dir}/[/]...[/]")
    code = _run_alembic("init", migrations_dir)
    if code != 0:
        raise typer.Exit(code)

    if model_import:
        from aura.orm.migrations import generate_env_py

        env_path = Path(migrations_dir) / "env.py"
        env_path.write_text(generate_env_py(Path(migrations_dir), model_import))
        console.print(f"  [green]Generated[/] {env_path} (models: {model_import})")

    console.print("[green]Alembic initialised.[/]")
    console.print(
        "\n[bold]Next:[/] Edit [cyan]alembic.ini[/] to set your database URL, "
        "then run [cyan]aura migrate make 'initial'[/]."
    )

"""``aura migrate`` commands — Alembic wrapper with improved UX."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    help="Database migration commands (Alembic wrapper).",
    invoke_without_command=True,
)
console = Console()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _generate_alembic_ini(migrations_dir: str, db_url: str) -> str:
    """Generate the content for an ``alembic.ini`` file.

    Args:
        migrations_dir: Path to the migrations directory (used as script_location).
        db_url: SQLAlchemy database URL.

    Returns:
        String content for ``alembic.ini``.
    """
    return f"""\
[alembic]
script_location = {migrations_dir}
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = {db_url}

[post_write_hooks]

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %%H:%%M:%%S
"""


# ---------------------------------------------------------------------------
# Callback — show command table when invoked without a sub-command
# ---------------------------------------------------------------------------


@app.callback()
def _list_commands(ctx: typer.Context) -> None:
    """Database migration commands (Alembic wrapper)."""
    if ctx.invoked_subcommand is not None:
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
        expand=False,
    )
    table.add_column("Command", style="bold", min_width=18)
    table.add_column("What it does")

    rows = [
        ("init", "Set up Alembic in this project"),
        ("make [message]", "Create a new migration (auto-detects model changes)"),
        ("up [revision]", "Apply pending migrations"),
        ("down [revision]", "Revert last migration"),
        ("stamp [revision]", "Mark DB at revision without running migrations"),
        ("reset", "⚠  Drop everything and re-apply all migrations from scratch"),
        ("status", "Show current state and history"),
    ]
    for cmd, desc in rows:
        table.add_row(cmd, desc)

    console.print(table)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("make")
def make_migration(
    message: str | None = typer.Argument(
        None,
        help="Short description of the migration (default: current timestamp)",
    ),
    autogenerate: bool = typer.Option(
        True,
        "--autogenerate/--no-autogenerate",
        help="Auto-detect model changes",
    ),
    migrations_dir: str = typer.Option(
        "migrations", "--dir", help="Alembic migrations directory"
    ),
) -> None:
    """Create a new migration revision.

    If *message* is omitted a timestamp is used automatically.

    Examples::

        aura migrate make
        aura migrate make "add users table"
        aura migrate make "add index on email" --no-autogenerate
    """
    msg = message if message is not None else datetime.now().strftime("%Y%m%d_%H%M%S")

    with console.status("[bold cyan]Creating migration...[/]", spinner="dots"):
        extra = ["--autogenerate"] if autogenerate else []
        code = _run_alembic("revision", *extra, "--message", msg)

    if code == 0:
        console.print(
            Panel(
                f"[bold green]Migration created[/]\n\n"
                f"[dim]Message: [cyan]{msg}[/]\n"
                f"[dim]Run [cyan]aura migrate up[/] to apply[/]",
                title="[bold cyan]Migration Ready[/]",
                border_style="green",
                expand=False,
            )
        )
    else:
        console.print(
            Panel(
                "[red]Failed to create migration[/]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(code)


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
    with console.status(
        f"[bold cyan]Applying migrations up to [cyan]{revision}[/]...[/]",
        spinner="dots",
    ):
        code = _run_alembic("upgrade", revision)

    if code == 0:
        console.print(
            Panel(
                f"[bold green]Migrations applied[/] up to [cyan]{revision}[/]",
                border_style="green",
                expand=False,
            )
        )
    else:
        console.print(
            Panel("[red]Migration upgrade failed[/]", border_style="red", expand=False)
        )
        raise typer.Exit(code)


@app.command("down")
def migrate_down(
    revision: str = typer.Argument(
        "-1", help="Target revision (default: -1 = one step back)"
    ),
) -> None:
    """Revert migrations (downgrade).

    Examples::

        aura migrate down        # revert last migration
        aura migrate down -2     # revert last two
        aura migrate down base   # revert all
    """
    with console.status(
        f"[bold yellow]Reverting migrations to [cyan]{revision}[/]...[/]",
        spinner="dots",
    ):
        code = _run_alembic("downgrade", revision)

    if code == 0:
        console.print(
            Panel(
                f"[bold yellow]Migrations reverted[/] to [cyan]{revision}[/]",
                border_style="yellow",
                expand=False,
            )
        )
    else:
        console.print(
            Panel("[red]Migration downgrade failed[/]", border_style="red", expand=False)
        )
        raise typer.Exit(code)


@app.command("status")
def migrate_status() -> None:
    """Show the current migration state."""
    console.print(
        Panel(
            "[bold]Migration Status[/]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()
    console.print("[bold]Current:[/]\n")
    _run_alembic("current")
    console.print()
    console.print("[bold]History:[/]\n")
    _run_alembic("history", "--verbose")


@app.command("stamp")
def migrate_stamp(
    revision: str = typer.Argument("head", help="Revision to stamp (default: head)"),
) -> None:
    """Mark the database as being at a specific revision without running migrations.

    Useful when you already have the schema and just need to initialise the
    migration state.

    Examples::

        aura migrate stamp head   # mark as fully migrated
        aura migrate stamp base   # mark as empty
        aura migrate stamp abc123 # mark at specific revision
    """
    with console.status(
        f"[bold cyan]Stamping database at [cyan]{revision}[/]...[/]",
        spinner="dots",
    ):
        code = _run_alembic("stamp", revision)

    if code == 0:
        console.print(
            Panel(
                f"[bold green]Database stamped[/] at [cyan]{revision}[/]",
                border_style="green",
                expand=False,
            )
        )
    else:
        console.print(
            Panel("[red]Stamp failed[/]", border_style="red", expand=False)
        )
        raise typer.Exit(code)


@app.command("reset")
def migrate_reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
) -> None:
    """Drop all data and re-apply every migration from scratch.

    Equivalent to ``down base`` followed by ``up head``.
    Use only in development — this is irreversible.

    Examples::

        aura migrate reset          # asks for confirmation
        aura migrate reset --yes    # skips confirmation (CI / scripts)
    """
    console.print(
        Panel(
            "[bold red]⚠  WARNING — This will destroy all data[/]\n\n"
            "  1. [yellow]downgrade base[/] — reverts every migration (drops all tables)\n"
            "  2. [green]upgrade head[/]  — re-applies all migrations from scratch\n\n"
            "[dim]Use only in development environments.[/]",
            title="[bold red]aura migrate reset[/]",
            border_style="red",
            expand=False,
        )
    )

    if not yes:
        typer.confirm("\nAre you sure you want to reset the database?", abort=True)

    console.print()
    with console.status(
        "[bold yellow]Reverting all migrations (downgrade base)...[/]", spinner="dots"
    ):
        down_code = _run_alembic("downgrade", "base")

    if down_code != 0:
        console.print(
            Panel("[red]Downgrade failed — reset aborted[/]", border_style="red", expand=False)
        )
        raise typer.Exit(down_code)

    console.print("[dim]  ✓ downgrade base[/]")

    with console.status(
        "[bold cyan]Re-applying all migrations (upgrade head)...[/]", spinner="dots"
    ):
        up_code = _run_alembic("upgrade", "head")

    if up_code != 0:
        console.print(
            Panel(
                "[red]Upgrade failed — database may be in a partial state[/]",
                border_style="red",
                expand=False,
            )
        )
        raise typer.Exit(up_code)

    console.print(
        Panel(
            "[bold green]✓ Database reset complete[/]\n\n"
            "[dim]All tables dropped and recreated from migrations.[/]",
            border_style="green",
            expand=False,
        )
    )


@app.command("init")
def migrate_init(
    migrations_dir: str = typer.Argument("migrations", help="Directory to create"),
    model_import: str | None = typer.Option(
        None,
        "--models",
        help="Import path for your AuraModel base, e.g. 'myapp.models:Base'",
    ),
    db_url: str = typer.Option(
        "sqlite+aiosqlite:///./dev.db",
        "--url",
        help="Database URL written into alembic.ini",
    ),
) -> None:
    """Initialise a new Alembic migrations environment.

    Creates the ``migrations/`` directory with ``env.py`` and a custom
    ``alembic.ini`` (without invoking the ``alembic init`` subprocess).

    Examples::

        aura migrate init
        aura migrate init --models myapp.models:Base
        aura migrate init --url postgresql+asyncpg://localhost/mydb
    """
    migrations_path = Path(migrations_dir)

    with console.status(
        f"[bold cyan]Initialising migrations in [cyan]{migrations_dir}/[/]...[/]",
        spinner="dots",
    ):
        # Create directory structure
        versions_path = migrations_path / "versions"
        versions_path.mkdir(parents=True, exist_ok=True)

        # Write alembic.ini next to the migrations dir
        ini_path = Path("alembic.ini")
        ini_path.write_text(
            _generate_alembic_ini(migrations_dir, db_url), encoding="utf-8"
        )

        # Generate env.py
        from aura.orm.migrations import generate_env_py

        env_path = migrations_path / "env.py"
        env_path.write_text(
            generate_env_py(migrations_path, model_import), encoding="utf-8"
        )

        # Write a minimal script.py.mako if it doesn't exist
        mako_path = migrations_path / "script.py.mako"
        if not mako_path.exists():
            mako_path.write_text(
                '"""${message}\n\n'
                "Revision ID: ${up_revision}\n"
                "Revises: ${down_revision | comma,n}\n"
                "Create Date: ${create_date}\n\n"
                '"""\n'
                "from __future__ import annotations\n\n"
                "from typing import Sequence, Union\n\n"
                "from alembic import op\n"
                "import sqlalchemy as sa\n"
                "${imports if imports else ''}\n\n"
                "# revision identifiers, used by Alembic.\n"
                "revision: str = ${repr(up_revision)}\n"
                "down_revision: Union[str, None] = ${repr(down_revision)}\n"
                "branch_labels: Union[str, Sequence[str], None] = "
                "${repr(branch_labels)}\n"
                "depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}\n\n\n"
                "def upgrade() -> None:\n"
                "    ${upgrades if upgrades else 'pass'}\n\n\n"
                "def downgrade() -> None:\n"
                "    ${downgrades if downgrades else 'pass'}\n",
                encoding="utf-8",
            )

    models_note = (
        f"[dim]Models: [cyan]{model_import}[/][/]"
        if model_import
        else "[dim]Models: [cyan]auto-discovered[/] from [cyan]modules/**/models.py[/][/]"
    )
    console.print(
        Panel(
            f"[bold green]Migrations initialised[/]\n\n"
            f"[dim]Directory:  [cyan]{migrations_dir}/[/][/]\n"
            f"[dim]Config:     [cyan]alembic.ini[/][/]\n"
            f"[dim]DB URL:     [cyan]{db_url}[/][/]\n"
            f"{models_note}\n\n"
            f"[bold]Next steps:[/]\n"
            f"  1. Review [cyan]alembic.ini[/] and update the database URL if needed\n"
            f"  2. Run [cyan]aura migrate make 'initial'[/] to create your first migration\n"
            f"  3. Run [cyan]aura migrate up[/] to apply it",
            title="[bold cyan]Alembic Ready[/]",
            border_style="green",
            expand=False,
        )
    )

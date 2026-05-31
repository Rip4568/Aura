"""Aura CLI entry point."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.console import Console

app = typer.Typer(
    name="aura",
    help="[bold cyan]Aura Framework CLI[/] — Modern async Python web development.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Show Aura Framework version."""
    try:
        from aura import __version__
    except ImportError:
        __version__ = "0.1.0"
    rprint(f"[bold cyan]Aura Framework[/] v{__version__}")


# ---------------------------------------------------------------------------
# Register sub-command groups
# ---------------------------------------------------------------------------
from aura.cli.commands import generate, migrate, new, run, tinker, worker  # noqa: E402

app.add_typer(new.app, name="new", help="Scaffold a new Aura project or resource.")
app.add_typer(generate.app, name="generate", help="Generate modules, schemas, guards, etc.")
app.command("run")(run.run_command)
app.command("worker")(worker.worker_command)
app.add_typer(migrate.app, name="migrate", help="Database migration commands.")
app.add_typer(tinker.app, name="tinker", help="Interactive REPL shell with auto-imported resources.")


if __name__ == "__main__":
    app()

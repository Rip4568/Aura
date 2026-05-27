"""``aura run`` command — start the Aura development or production server."""

from __future__ import annotations

import typer
from rich.console import Console

console = Console()


def run_command(
    app_path: str = typer.Argument("main:app", help="App path as module:variable (e.g. main:app)"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable hot-reload (dev only)"),
    workers: int = typer.Option(1, "--workers", "-w", help="Number of worker processes"),
    log_level: str = typer.Option("info", "--log-level", help="Uvicorn log level"),
) -> None:
    """Run the Aura application server via uvicorn.

    In development, pass ``--reload`` for automatic code reloading.

    Examples::

        aura run                          # default: main:app on 127.0.0.1:8000
        aura run myapp.main:app --reload  # custom module, hot-reload
        aura run --port 9000 --workers 4  # production-like
    """
    console.print(f"[bold cyan]Aura[/] starting on [bold]{host}:{port}[/]")
    console.print(f"  App: [cyan]{app_path}[/]")
    if reload:
        console.print("  Mode: [yellow]development (hot-reload enabled)[/]")
    else:
        console.print(f"  Workers: [cyan]{workers}[/]")

    try:
        import uvicorn  # type: ignore[import]
    except ImportError:
        console.print(
            "[red]uvicorn is not installed.[/] "
            "Run: [bold]pip install uvicorn[standard][/]"
        )
        raise typer.Exit(1)

    uvicorn.run(
        app_path,
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level=log_level,
    )

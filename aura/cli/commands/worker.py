"""``aura worker`` command — run the Aura background task worker."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

console = Console()


def worker_command(
    queues: list[str] = typer.Option(
        ["default"],
        "--queue",
        "-q",
        help="Queue(s) to consume from (repeat for multiple)",
    ),
    concurrency: int = typer.Option(4, "--concurrency", "-c", help="Max concurrent tasks"),
    burst: bool = typer.Option(
        False,
        "--burst",
        "-b",
        help="Exit after draining existing jobs",
    ),
    app_path: str = typer.Option(
        None,
        "--app",
        "-a",
        help="Import path for the Aura app (to load registered tasks), e.g. 'main:app'",
    ),
) -> None:
    """Start the Aura background worker.

    The worker processes tasks enqueued via ``@task``-decorated functions.

    Examples::

        aura worker                              # default queue, 4 concurrency
        aura worker -q emails -q default -c 8   # multiple queues
        aura worker --burst                      # process then exit
        aura worker --app myapp.main:app         # load app to register tasks
    """
    if app_path:
        _import_app(app_path)

    from aura.jobs.worker import AuraWorker

    worker = AuraWorker(
        queues=list(queues),
        concurrency=concurrency,
        burst=burst,
    )

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/]")


def _import_app(app_path: str) -> None:
    """Import the Aura app from *module:variable* notation to register tasks."""
    import importlib

    try:
        module_path, attr = app_path.rsplit(":", 1)
    except ValueError:
        console.print(f"[red]Invalid app path:[/] {app_path!r}. Expected 'module:variable'.")
        raise typer.Exit(1)

    try:
        module = importlib.import_module(module_path)
        getattr(module, attr)
    except (ImportError, AttributeError) as exc:
        console.print(f"[red]Could not import app:[/] {exc}")
        raise typer.Exit(1)

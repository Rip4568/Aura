"""``aura db:seed`` command."""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel

from aura.di.container import Lifetime, container
from aura.orm.factories import Factory
from aura.orm.seeders import Seeder
from aura.orm.session import current_session, db

console = Console()
app = typer.Typer(
    help="Database seeding commands.",
    invoke_without_command=True,
)


def discover_seeders(root_dir: str = ".") -> dict[str, type[Seeder]]:
    """Recursively search CWD to find and import Seeder classes.

    Args:
        root_dir: The directory to start searching from.

    Returns:
        A dictionary mapping seeder class names to their classes.
    """
    discovered: dict[str, type[Seeder]] = {}
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    exclude_dirs = {
        ".git",
        ".venv",
        "venv",
        "tests",
        "migrations",
        "__pycache__",
        "storage",
        "dist",
        "build",
    }

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            if not filename.endswith(".py") or filename.startswith("__"):
                continue

            rel_path = os.path.relpath(os.path.join(dirpath, filename), root_dir)
            module_name = rel_path[:-3].replace(os.path.sep, ".")

            try:
                mod = importlib.import_module(module_name)
            except Exception:
                continue

            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if obj.__module__ != module_name:
                    continue
                try:
                    if issubclass(obj, Seeder) and obj is not Seeder:
                        discovered[name] = obj
                except Exception:
                    pass
    return discovered


def discover_factories(root_dir: str = ".") -> dict[str, type[Factory[Any]]]:
    """Recursively search CWD to find and import Factory classes.

    Args:
        root_dir: The directory to start searching from.

    Returns:
        A dictionary mapping factory class names to their classes.
    """
    discovered: dict[str, type[Factory[Any]]] = {}
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    exclude_dirs = {
        ".git",
        ".venv",
        "venv",
        "tests",
        "migrations",
        "__pycache__",
        "storage",
        "dist",
        "build",
    }

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            if not filename.endswith(".py") or filename.startswith("__"):
                continue

            rel_path = os.path.relpath(os.path.join(dirpath, filename), root_dir)
            module_name = rel_path[:-3].replace(os.path.sep, ".")

            try:
                mod = importlib.import_module(module_name)
            except Exception:
                continue

            for name, obj in inspect.getmembers(mod, inspect.isclass):
                if obj.__module__ != module_name:
                    continue
                try:
                    if issubclass(obj, Factory) and obj is not Factory:
                        discovered[name] = obj
                except Exception:
                    pass
    return discovered


def setup_database_manager() -> str | None:
    """Initialize DatabaseManager and return the database URL."""
    db_url = os.environ.get("AURA__DATABASE__URL") or os.environ.get("DATABASE__URL")
    db_echo = False

    # Try loading from local aura.toml config
    if not db_url:
        toml_path = os.path.join(os.getcwd(), "aura.toml")
        if os.path.exists(toml_path):
            try:
                if sys.version_info >= (3, 11):
                    import tomllib
                else:
                    import tomli as tomllib  # type: ignore[import-not-found]

                with open(toml_path, "rb") as f:
                    config_data = tomllib.load(f)

                db_section = config_data.get("database", {})
                db_url = db_section.get("url")
                db_echo = db_section.get("echo", False)
            except Exception:
                pass

    # Try fallback to loader/base config
    if not db_url:
        try:
            from aura.config.base import AuraConfig

            cfg = AuraConfig()
            db_url = cfg.database.url
            db_echo = cfg.database.echo
        except Exception:
            pass

    if db_url:
        try:
            db.init(db_url, echo=db_echo)
            return db_url
        except Exception:
            pass

    return db_url


def is_production_env(db_url: str | None) -> bool:
    """Check if the current execution is in a production environment.

    Args:
        db_url: The database URL to check.

    Returns:
        True if production, False otherwise.
    """
    env_val = os.environ.get("AURA_ENV") or os.environ.get("ENV")
    if env_val and env_val.lower() == "production":
        return True
    if db_url:
        lower_url = db_url.lower()
        if "prod" in lower_url or "production" in lower_url:
            return True
    return False


def sync(coroutine: Any) -> Any:
    """Helper to execute async coroutine synchronously in Typer command."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coroutine)


@app.callback(invoke_without_command=True)
def seed(
    ctx: typer.Context,
    class_name: str = typer.Option(
        "DatabaseSeeder",
        "--class",
        "-c",
        help="The seeder class to execute (default: DatabaseSeeder)",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Skip seeders that have already run (tracks in _aura_seeded)",
    ),
) -> None:
    """Run database seeders."""
    if ctx.invoked_subcommand is not None:
        return

    # Ensure CWD is in path
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # 1. Initialize database manager
    db_url = setup_database_manager()
    if not db_url:
        console.print("[red]Error: Database not configured or unavailable.[/]")
        raise typer.Exit(1)

    # 2. Check for production
    if is_production_env(db_url):
        console.print(
            Panel(
                "[bold red][Warning] WARNING: You are running in a PRODUCTION environment![/]",
                border_style="red",
                title="[bold red]Production Alert[/]",
            )
        )
        confirm = typer.confirm("Are you sure you want to run the database seeders?", default=False)
        if not confirm:
            console.print("[yellow]Operation aborted by user.[/]")
            raise typer.Exit(1)

    # 3. Discover app instance in main.py to pull registry & DI providers
    try:
        from aura import Aura

        main_mod = importlib.import_module("main")
        for _, obj in inspect.getmembers(main_mod):
            if isinstance(obj, Aura):
                # Startup container to register all modules and providers
                sync(obj.container.startup())
                # Update global container providers with the ones registered in the app
                container._providers.update(obj.container._providers)
                break
    except Exception:
        pass

    # Discover and register factories in container
    factories = discover_factories(cwd)
    for factory_class in factories.values():
        if not container.is_registered(factory_class):
            container.register(factory_class, lifetime=Lifetime.TRANSIENT)

    # 4. Discover seeders recursively
    seeders = discover_seeders(cwd)
    if class_name not in seeders:
        console.print(f"[red]Error: Seeder class '{class_name}' not found.[/]")
        console.print("[dim]Discovered seeders in project:[/] " + ", ".join(seeders.keys()))
        raise typer.Exit(1)

    target_seeder = seeders[class_name]

    # 5. Execute seeder
    try:
        sync(run_seeder(target_seeder, once))
    except Exception as exc:
        console.print(f"[bold red]Seeding failed with error:[/] {exc}")
        import traceback

        traceback.print_exc()
        raise typer.Exit(1)


async def run_seeder(seeder_cls: type[Seeder], once: bool) -> None:
    """Run the target seeder within an active connection transaction.

    Args:
        seeder_cls: The Seeder class to execute.
        once: If True, tracks and skips already run seeders.
    """
    from aura.orm.seeders import ensure_seeded_table_exists, has_seeded, mark_as_seeded

    async with db.session() as session:
        await ensure_seeded_table_exists(session)

    if once:
        async with db.session() as session:
            already_seeded = await has_seeded(session, seeder_cls.__name__)
        if already_seeded:
            console.print(
                f"[yellow]Skipping seeder '{seeder_cls.__name__}' (already seeded once).[/]"
            )
            return

    console.print(f"[bold cyan]Running database seeder:[/] [magenta]{seeder_cls.__name__}[/]")

    # Ensure registered in global container
    if not container.is_registered(seeder_cls):
        meta = getattr(seeder_cls, "__aura_injectable__", None)
        lifetime = meta["lifetime"] if meta else Lifetime.SINGLETON
        container.register(seeder_cls, lifetime=lifetime)

    async with db.session() as session:
        token = current_session.set(session)
        try:
            seeder_instance = await container.resolve(seeder_cls)
            await seeder_instance.run()
            if once:
                await mark_as_seeded(session, seeder_cls.__name__)
        finally:
            current_session.reset(token)

    console.print(f"[bold green]Successfully seeded:[/] [cyan]{seeder_cls.__name__}[/]")

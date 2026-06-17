# ruff: noqa: N802
"""``aura tinker`` command.

Open an interactive REPL shell with auto-imported models and services.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
from typing import Any

import typer
from rich.console import Console

console = Console()
app = typer.Typer(help="Interactive shell commands.")


def sync(coroutine: Any) -> Any:
    """Helper function to execute async coroutines synchronously in standard Python REPL.

    Useful when top-level await is not natively available.
    """
    import asyncio

    try:
        import nest_asyncio  # type: ignore[import-not-found]

        nest_asyncio.apply()
    except ImportError:
        pass

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coroutine)


def discover_project_objects(root_dir: str = ".") -> dict[str, dict[str, Any]]:
    """Recursively search the CWD to import user-defined models, repositories, and services."""
    discovered: dict[str, dict[str, Any]] = {
        "models": {},
        "repositories": {},
        "services": {},
        "schemas": {},
        "others": {},
    }

    # Ensure CWD is first in sys.path
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
        # Filter directories in-place to avoid traversing them
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        for filename in filenames:
            if not filename.endswith(".py") or filename.startswith("__"):
                continue

            # Calculate qualified module name
            rel_path = os.path.relpath(os.path.join(dirpath, filename), root_dir)
            module_name = rel_path[:-3].replace(os.path.sep, ".")

            try:
                mod = importlib.import_module(module_name)
            except Exception:
                continue

            for name, obj in inspect.getmembers(mod, inspect.isclass):
                # Only register classes declared in the scanned module
                if obj.__module__ != module_name:
                    continue

                # Scan for models and repositories (optional imports)
                try:
                    from aura.orm import AuraModel, Repository

                    if issubclass(obj, AuraModel) and obj is not AuraModel:
                        discovered["models"][name] = obj
                        continue
                    if issubclass(obj, Repository) and obj is not Repository:
                        discovered["repositories"][name] = obj
                        continue
                except ImportError:
                    pass

                # Scan for schemas (DTOs)
                try:
                    from aura import Schema

                    if issubclass(obj, Schema) and obj is not Schema:
                        discovered["schemas"][name] = obj
                        continue
                except ImportError:
                    pass

                # Scan for Services (either by name or @injectable)
                is_injectable = getattr(obj, "__aura_injectable__", None) is not None
                is_service_file = filename in ("service.py", "services.py")
                if is_injectable or name.endswith("Service") or is_service_file:
                    discovered["services"][name] = obj
                    continue

    return discovered


def setup_database_manager() -> Any | None:
    """Load configuration hierarchically and auto-initialize the DatabaseManager."""
    try:
        from aura.orm.session import db
    except ImportError:
        return None

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
            return db
        except Exception:
            pass

    return None


def run_ipython_shell(namespace: dict[str, Any]) -> None:
    """Launch IPython interative shell with autoawait enabled."""
    import IPython  # type: ignore[import-not-found]
    from traitlets.config import Config  # type: ignore[import-not-found]

    c = Config()
    c.InteractiveShell.autoawait = True
    c.InteractiveShellApp.gui = "asyncio"
    c.TerminalInteractiveShell.colors = "Neutral"

    IPython.start_ipython(argv=[], user_ns=namespace, config=c)


def run_bpython_shell(namespace: dict[str, Any]) -> None:
    """Launch bpython interactive shell if available."""
    import bpython  # type: ignore[import-not-found]

    bpython.embed(locals_=namespace)


def _print_welcome_banner(
    project_name: str,
    objects: dict[str, dict[str, Any]],
    db_active: bool,
    repl: str,
) -> None:
    """Print a highly polished ciano-to-purple banner with Rich detailing auto-imported assets."""
    banner = r"""
     _      _   _   ____        _
    / \    | | | | |  _ \      / \
   / _ \   | | | | | |_) |    / _ \
  / ___ \  | |_| | |  _ <    / ___ \
 /_/   \_\  \___/  |_| \_\  /_/   \_\  t i n k e r
"""
    console.print(f"[bold purple]{banner}[/]")
    console.print("-" * 70)
    console.print(
        f"[bold]App:[/] [cyan]{project_name}[/] | [bold]REPL Shell:[/] [magenta]{repl.upper()}[/]"
    )

    if db_active:
        console.print("[bold green]✓ Database 'db' initialized and connected.[/]")
    else:
        console.print("[bold yellow]⚠ Database offline or not configured.[/]")

    console.print("-" * 70)

    # Print discovered assets
    total_imports = 0
    for key, label, color in [
        ("models", "Models", "green"),
        ("repositories", "Repositories", "magenta"),
        ("services", "Services", "blue"),
        ("schemas", "Schemas", "cyan"),
    ]:
        items = list(objects[key].keys())
        if items:
            total_imports += len(items)
            console.print(f"[bold {color}]{label}:[/] {', '.join(items)}")

    if total_imports == 0:
        console.print("[dim]No local modules or components discovered in modules/ folder.[/]")

    console.print("-" * 70)
    if repl != "ipython":
        console.print(
            "[bold yellow]Async Tip:[/] Use [bold]sync(coroutine)[/] "
            "to run async calls in standard REPL."
        )
        console.print("Example: [cyan]users = sync(UserRepository(db.session()).list())[/]")
    else:
        console.print(
            "[bold green]Async Tip:[/] IPython supports top-level await! "
            "Run: [cyan]await db.session.execute(...)[/]"
        )
    console.print("-" * 70)


@app.callback(invoke_without_command=True)
def run_tinker(
    ctx: typer.Context,
    no_db: bool = typer.Option(
        False, "--no-db", help="Start shell without initializing the database"
    ),
    repl: str = typer.Option(
        "ipython", "--repl", help="Shell backend to use (ipython, bpython, python)"
    ),
) -> None:
    """Open an interactive Python shell configured with your Aura application.

    Automatically imports models, repositories, services, and schemas.
    IPython shell supports top-level await out of the box.
    """
    if ctx.invoked_subcommand is not None:
        return

    # 1. Adjust sys.path
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    # 2. Try to discover app instance in main.py
    app_instance = None
    project_name = "Aura App"
    try:
        from aura import Aura

        main_mod = importlib.import_module("main")
        for _, obj in inspect.getmembers(main_mod):
            if isinstance(obj, Aura):
                app_instance = obj
                project_name = getattr(obj, "title", project_name)
                break
    except Exception:
        pass

    # 3. Setup database manager
    db = None
    if not no_db:
        db = setup_database_manager()

    # 4. Discover user objects recursively
    project_objects = discover_project_objects(cwd)

    # 5. Populate interactive REPL namespace
    namespace: dict[str, Any] = {
        "sync": sync,
    }

    if db is not None:
        namespace["db"] = db

    if app_instance is not None:
        namespace["app"] = app_instance
        namespace["container"] = app_instance.container

        # Gracefully startup/warmup the DI container synchronously
        try:
            sync(app_instance.container.startup())
        except Exception:
            pass

    # Add core imports for ease of use
    try:
        from aura.orm import Q

        namespace["Q"] = Q
    except ImportError:
        pass

    try:
        from aura.logging import Log

        namespace["Log"] = Log
    except ImportError:
        pass

    # Inject discovered models, services, etc.
    for category in ["models", "repositories", "services", "schemas"]:
        for name, cls in project_objects[category].items():
            namespace[name] = cls

    # 6. Display Welcome Banner
    _print_welcome_banner(project_name, project_objects, db is not None, repl)

    # 7. Start the selected shell
    if repl == "ipython":
        try:
            run_ipython_shell(namespace)
            return
        except ImportError:
            console.print("[yellow]IPython not installed. Falling back to standard REPL...[/]")
            console.print(
                "[dim]Hint: Install IPython for top-level await: pip install ipython[/]\n"
            )

    if repl == "bpython":
        try:
            run_bpython_shell(namespace)
            return
        except ImportError:
            console.print("[yellow]bpython not installed. Falling back to standard REPL...[/]\n")

    # Standard Python REPL
    import code

    code.interact(banner="", local=namespace)

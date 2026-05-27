"""``aura new`` command — scaffold a new Aura project."""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="Create a new Aura project.")
console = Console()

# ---------------------------------------------------------------------------
# Project template
# ---------------------------------------------------------------------------

_MAIN_PY = '''\
"""Entry point for {project_name}."""
from aura import Aura

app = Aura()

# Import your modules here
# from {snake_name}.modules.users.module import UsersModule
# app.register(UsersModule)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
'''

_AURA_TOML = '''\
[app]
name = "{project_name}"
debug = true

[server]
host = "127.0.0.1"
port = 8000

[database]
url = "sqlite+aiosqlite:///./{snake_name}.db"
'''

_EXAMPLE_MODULE_INIT = '''\
"""Example module — remove or replace as needed."""
'''

_EXAMPLE_MODULE_PY = '''\
"""Example Aura module."""
# from aura.modules import AuraModule
# from .router import router
#
# class ExampleModule(AuraModule):
#     routers = [router]
'''

_GITIGNORE = '''\
__pycache__/
*.py[cod]
*.pyo
.env
.venv
venv/
env/
*.egg-info/
dist/
build/
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.db
*.sqlite3
migrations/versions/*.py
!migrations/versions/.gitkeep
'''

_TESTS_INIT = '''\
"""Test suite for {project_name}."""
'''

_CONFTEST = '''\
"""Pytest configuration for {project_name}."""
import pytest
from aura.testing import AuraTestClient

# Import your app
# from main import app as aura_app


# @pytest.fixture
# async def client():
#     async with AuraTestClient(aura_app) as c:
#         yield c
'''

_PYPROJECT_TOML = '''\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{project_name}"
version = "0.1.0"
description = "An Aura Framework application"
requires-python = ">=3.11"
dependencies = [
    "aura-framework>=0.1.0",
    "uvicorn[standard]>=0.27",
    "aiosqlite>=0.20",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-asyncio>=0.23",
    "httpx>=0.26",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
'''


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _to_snake(name: str) -> str:
    """Convert a project name to snake_case."""
    name = re.sub(r"[-\s]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    return name.lower()


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

@app.command("project")
def new_project(
    project_name: str = typer.Argument(..., help="Name of the new project"),
    directory: str = typer.Option(".", "--dir", "-d", help="Parent directory for the project"),
) -> None:
    """Scaffold a brand-new Aura project with a complete starter structure."""
    snake = _to_snake(project_name)
    target = Path(directory) / snake

    if target.exists():
        console.print(f"[red]Error:[/] Directory '{target}' already exists.")
        raise typer.Exit(1)

    files: dict[Path, str] = {
        target / "main.py": _MAIN_PY.format(project_name=project_name, snake_name=snake),
        target / "aura.toml": _AURA_TOML.format(project_name=project_name, snake_name=snake),
        target / "pyproject.toml": _PYPROJECT_TOML.format(project_name=project_name, snake_name=snake),
        target / ".gitignore": _GITIGNORE,
        target / f"{snake}/__init__.py": f'"""Application package for {project_name}."""\n',
        target / f"{snake}/modules/__init__.py": _EXAMPLE_MODULE_INIT,
        target / f"{snake}/modules/example.py": _EXAMPLE_MODULE_PY,
        target / "tests/__init__.py": _TESTS_INIT.format(project_name=project_name),
        target / "tests/conftest.py": _CONFTEST.format(project_name=project_name),
    }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"Creating project [bold cyan]{project_name}[/]...", total=len(files))

        for file_path, content in files.items():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            progress.advance(task)

    console.print()
    console.print(
        Panel(
            f"[bold green]Project created successfully![/]\n\n"
            f"[bold]Next steps:[/]\n\n"
            f"  [cyan]cd {snake}[/]\n"
            f"  [cyan]pip install -e '.[dev]'[/]\n"
            f"  [cyan]aura run[/]",
            title=f"[bold cyan] {project_name}[/]",
            expand=False,
        )
    )


@app.callback(invoke_without_command=True)
def new_callback(ctx: typer.Context) -> None:
    """Create a new Aura project.

    Usage: ``aura new project <project-name>``
    """
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())

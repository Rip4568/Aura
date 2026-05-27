"""``aura generate`` command — scaffold modules, schemas, guards, and more."""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Generate Aura modules, schemas, guards, and other resources.")
console = Console()


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def _pascal(name: str) -> str:
    """Convert a name to PascalCase."""
    return "".join(word.capitalize() for word in re.split(r"[-_\s]+", name))


def _snake(name: str) -> str:
    """Convert a name to snake_case."""
    name = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return re.sub(r"[-\s]+", "_", name).lower()


def _plural(name: str) -> str:
    """Very simple pluralisation — append 's' if needed."""
    if name.endswith("s"):
        return name
    return name + "s"


def _singular(name: str) -> str:
    """Very simple singularisation — strip trailing 's' if present."""
    if name.endswith("s") and len(name) > 1:
        return name[:-1]
    return name


# ---------------------------------------------------------------------------
# File templates
# ---------------------------------------------------------------------------

def _schema_template(name: str) -> str:
    # Use singular form for class names (Product, not Products)
    singular_name = _singular(_snake(name))
    pascal = _pascal(singular_name)
    plural_label = _plural(_snake(name))
    return f'''\
"""Schemas for the {pascal} resource."""
from __future__ import annotations

from aura.schema import Schema


class {pascal}Base(Schema):
    """Shared fields for {pascal}."""
    name: str


class {pascal}Create({pascal}Base):
    """Payload for creating a new {pascal}."""


class {pascal}Update(Schema):
    """Payload for updating a {pascal} (all fields optional)."""
    name: str | None = None


class {pascal}Response({pascal}Base):
    """Response schema for {pascal}."""
    id: int

    model_config = {{"from_attributes": True}}
'''


def _service_template(name: str) -> str:
    pascal = _pascal(name)
    snake = _snake(name)
    return f'''\
"""Service layer for the {pascal} resource."""
from __future__ import annotations

from typing import Any


class {pascal}Service:
    """Business logic for {pascal} operations."""

    async def get_all(self) -> list[Any]:
        """Return all {_plural(snake)}."""
        # TODO: inject and use repository
        return []

    async def get_by_id(self, id: int) -> Any | None:
        """Return a single {snake} by id, or None."""
        # TODO: inject and use repository
        return None

    async def create(self, data: dict[str, Any]) -> Any:
        """Create and return a new {snake}."""
        # TODO: inject and use repository
        return data

    async def update(self, id: int, data: dict[str, Any]) -> Any | None:
        """Update a {snake} and return the updated record."""
        # TODO: inject and use repository
        return data

    async def delete(self, id: int) -> bool:
        """Delete a {snake}. Returns True if deleted."""
        # TODO: inject and use repository
        return True
'''


def _router_template(name: str) -> str:
    pascal = _pascal(name)
    snake = _snake(name)
    plural = _plural(snake)
    return f'''\
"""Router for the {pascal} resource."""
from __future__ import annotations

from typing import Any

import typer
from aura.routing import Router

router = Router(prefix="/{plural}", tags=["{pascal}"])


@router.get("/")
async def list_{plural}() -> list[Any]:
    """List all {plural}."""
    return []


@router.get("/{{id}}")
async def get_{snake}(id: int) -> Any:
    """Get a {snake} by id."""
    return {{"id": id}}


@router.post("/")
async def create_{snake}(data: dict[str, Any]) -> Any:
    """Create a new {snake}."""
    return data


@router.put("/{{id}}")
async def update_{snake}(id: int, data: dict[str, Any]) -> Any:
    """Update a {snake}."""
    return data


@router.delete("/{{id}}")
async def delete_{snake}(id: int) -> dict[str, bool]:
    """Delete a {snake}."""
    return {{"deleted": True}}
'''


def _module_template(name: str) -> str:
    pascal = _pascal(name)
    snake = _snake(name)
    return f'''\
"""Aura module for the {pascal} feature."""
from __future__ import annotations

# from aura.modules import AuraModule
# from .router import router
# from .service import {pascal}Service


# class {pascal}Module(AuraModule):
#     """Module encapsulating {pascal} feature routes and services."""
#
#     routers = [router]
#     providers = [{pascal}Service]
'''


def _guard_template(name: str) -> str:
    pascal = _pascal(name)
    return f'''\
"""Guard: {pascal}Guard — controls access to protected routes."""
from __future__ import annotations

from typing import Any

# from aura.guards import Guard, GuardContext


# class {pascal}Guard(Guard):
#     """
#     {pascal} guard implementation.
#
#     Return True to allow the request through, False to block with 403.
#
#     Example::
#
#         @router.get("/admin", guards=[{pascal}Guard])
#         async def admin_panel(): ...
#     """
#
#     async def can_activate(self, ctx: GuardContext) -> bool:
#         # Implement your guard logic here
#         return True
'''


# ---------------------------------------------------------------------------
# Shared creation helper
# ---------------------------------------------------------------------------

def _write_file(path: Path, content: str, force: bool = False) -> bool:
    """Write *content* to *path*.  Returns True if written, False if skipped."""
    if path.exists() and not force:
        console.print(f"  [yellow]skip[/]  {path} (already exists)")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    console.print(f"  [green]create[/] {path}")
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command("module")
def generate_module(
    name: str = typer.Argument(..., help="Module name (e.g. 'users' or 'blog-posts')"),
    output: str = typer.Option(".", "--out", "-o", help="Output base directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
) -> None:
    """Generate a complete Aura module (schema, service, router, module)."""
    snake = _snake(name)
    base = Path(output) / snake

    files = {
        base / "schema.py": _schema_template(name),
        base / "service.py": _service_template(name),
        base / "router.py": _router_template(name),
        base / "module.py": _module_template(name),
        base / "__init__.py": f'"""Aura module: {_pascal(name)}."""\n',
    }

    console.print(f"\n[bold]Generating module [cyan]{_pascal(name)}[/]...[/]\n")
    for path, content in files.items():
        _write_file(path, content, force)

    console.print(f"\n[bold green]Module '{_pascal(name)}' generated at {base}[/]")


@app.command("schema")
def generate_schema(
    name: str = typer.Argument(..., help="Schema name (e.g. 'user')"),
    output: str = typer.Option(".", "--out", "-o", help="Output directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing file"),
) -> None:
    """Generate a Pydantic schema file for a resource."""
    snake = _snake(name)
    path = Path(output) / f"{snake}_schema.py"

    console.print(f"\n[bold]Generating schema [cyan]{_pascal(name)}Schema[/]...[/]\n")
    _write_file(path, _schema_template(name), force)
    console.print(f"\n[bold green]Schema generated at {path}[/]")


@app.command("guard")
def generate_guard(
    name: str = typer.Argument(..., help="Guard name (e.g. 'auth' or 'admin')"),
    output: str = typer.Option(".", "--out", "-o", help="Output directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing file"),
) -> None:
    """Generate a Guard class stub."""
    snake = _snake(name)
    path = Path(output) / f"{snake}_guard.py"

    console.print(f"\n[bold]Generating guard [cyan]{_pascal(name)}Guard[/]...[/]\n")
    _write_file(path, _guard_template(name), force)
    console.print(f"\n[bold green]Guard generated at {path}[/]")

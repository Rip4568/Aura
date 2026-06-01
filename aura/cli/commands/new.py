"""``aura new`` command — scaffold a new Aura project with a working boilerplate."""

from __future__ import annotations

import re
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(help="Scaffold a new Aura project.")
console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snake(name: str) -> str:
    name = re.sub(r"[-\s]+", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    return name.lower()

def _pascal(name: str) -> str:
    return "".join(w.capitalize() for w in re.split(r"[-_\s]+", name))


# ---------------------------------------------------------------------------
# File templates — every file is READY TO RUN, nothing commented out
# ---------------------------------------------------------------------------

def _main_py(project_name: str, snake: str) -> str:
    return f'''\
"""
{project_name} — Aura Framework application.

Run:
    aura run                 # development
    aura run --reload        # with hot-reload
    aura run --workers 4     # production-like
"""
from aura import Aura, QueryCountMiddleware, SessionMiddleware
from starlette.middleware import Middleware
from aura.logging import RequestLogInterceptor
from aura.admin import AdminModule
from modules.users.module import UsersModule

app = Aura(
    modules=[UsersModule, AdminModule],
    middleware=[
        Middleware(SessionMiddleware, secret_key="change-me-in-production-32chars!!"),
        Middleware(RequestLogInterceptor),
        Middleware(QueryCountMiddleware),
    ],
    title="{project_name}",
    version="0.1.0",
    description="Built with Aura Framework",
)
'''

def _env_example() -> str:
    return """\
# Copy this file to .env and fill in the values.
# Aura reads nested config with __ as separator.

# App Config
AURA__APP_NAME="Aura App"
AURA__DEBUG=true
AURA__SECRET_KEY="change-me-in-production-32chars!!"
AURA_ADMIN_PASSWORD="minha-senha-secreta"


# Server
AURA__SERVER__HOST=127.0.0.1
AURA__SERVER__PORT=8000
AURA__SERVER__WORKERS=1
AURA__SERVER__RELOAD=true

# Database
AURA__DATABASE__URL=sqlite+aiosqlite:///./dev.db
# AURA__DATABASE__URL=postgresql+asyncpg://user:pass@localhost:5432/dbname
AURA__DATABASE__POOL_SIZE=5
AURA__DATABASE__MAX_OVERFLOW=10
AURA__DATABASE__ECHO=false

# Jobs
AURA__JOBS__BACKEND=memory
# AURA__JOBS__BACKEND=saq
# AURA__JOBS__BROKER_URL=redis://localhost:6379/0

# Logging
AURA__LOGGING__LEVEL=INFO
AURA__LOGGING__DIR=storage/logs
AURA__LOGGING__FORMAT=plain
AURA__LOGGING__CONSOLE=true
AURA__LOGGING__FILE=true
"""

def _aura_toml(project_name: str, snake: str) -> str:
    return f"""\
# General settings
app_name = "{project_name}"
debug = true
secret_key = "change-me-in-production-32chars!!"

[server]
host = "127.0.0.1"
port = 8000
workers = 1
reload = true

[database]
url = "sqlite+aiosqlite:///./{snake}.db"
pool_size = 5
max_overflow = 10
echo = false

[jobs]
backend = "memory"
broker_url = "redis://localhost:6379"
default_queue = "default"
max_workers = 4

[logging]
level = "INFO"
dir = "storage/logs"
format = "plain"
console = true
file = true
sanitize_fields = ["password", "token", "secret", "authorization", "cookie"]
include_request_body = false
include_response_body = false
"""

def _pyproject_toml(project_name: str) -> str:
    return f"""\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{project_name}"
version = "0.1.0"
description = "An Aura Framework application"
requires-python = ">=3.10"
dependencies = [
    "aura-web[uvicorn]>=0.1.0",
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
"""

def _readme(project_name: str) -> str:
    return f"""\
# {project_name}

Built with [Aura Framework](https://pypi.org/project/aura-web/).

## Quick start

```bash
# Install dependencies
pip install -e ".[dev]"

# Copy env file and configure
cp .env.example .env

# Run database seeders (optional)
aura db seed

# Run development server
aura run --reload

# Open in browser
# API docs:  http://localhost:8000/docs
# Health:    http://localhost:8000/health
```

## Project structure

```
{_snake(project_name)}/
├── main.py                  # Entry point
├── aura.toml                # App config
├── .env                     # Secrets (not committed)
├── database/                # Database seeders and factories
│   ├── seeders/
│   │   ├── user_seeder.py   # Seeder for User model
│   │   └── database_seeder.py # Main seeder entrypoint
│   └── factories/
│       └── user_factory.py  # Factory for generating fake Users
├── modules/
│   └── users/               # Example module — duplicate for new features
│       ├── module.py        # @Module declaration
│       ├── controller.py    # Route handlers
│       ├── service.py       # Business logic (@injectable)
│       ├── schemas.py       # Pydantic DTOs (the Spec)
│       ├── models.py        # ORM database model
│       └── repositories.py  # Database Repository
└── tests/
    └── test_users.py        # Integration tests
```

## Database Seeders

Aura provides a native asynchronous database seeding system with dependency injection support.

To seed your database:
```bash
# Run the main DatabaseSeeder (which runs UserSeeder)
aura db seed

# Run a specific seeder class
aura db seed --class UserSeeder

# Run idempotently (skips seeders already registered in _aura_seeded)
aura db seed --once
```

You can generate a new seeder with:
```bash
aura generate seeder post
```

## Model Factories & Faker

Aura has a modern **Factories** system integrated with **Faker** to easily
generate realistic mock data for your integration tests and seeders.

Your factories live in `database/factories/`. For example, `UserFactory` generates random users:

```python
from database.factories.user_factory import UserFactory

# 1. Generate in-memory instances (fast, does not touch the database)
user = UserFactory().make(name="John Doe")
users = UserFactory().make_many(5)

# 2. Persist in the database (automatically handles async transactions)
user = await UserFactory().create(email="john@example.com")
users = await UserFactory().create_many(5)
```

You can generate a new factory with:
```bash
aura generate factory post
```

A working demonstration of using `UserFactory` is included in
`tests/test_users.py` (`test_user_factory_demo`).

## Adding a new module

```bash
aura generate module posts
```

Then import the new module in `main.py`:

```python
from modules.posts.module import PostsModule

app = Aura(modules=[UsersModule, PostsModule], ...)
```

## Running tests

```bash
pytest
```
"""

def _gitignore() -> str:
    return """\
__pycache__/
*.py[cod]
*.pyo
.env
.venv/
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
"""

# ---- modules/users/ --------------------------------------------------------

def _users_models() -> str:
    return '''\
"""ORM model for the Users module."""

from __future__ import annotations

from aura.orm import AuraModel, CharField, EmailField
from sqlalchemy.orm import Mapped


class User(AuraModel):
    __tablename__ = "users"

    name: Mapped[str] = CharField(max_length=150)
    email: Mapped[str] = EmailField(unique=True)
'''

def _users_repositories() -> str:
    return '''\
"""Repository for the Users module."""

from __future__ import annotations

from aura import Repository, injectable
from .models import User


@injectable
class UserRepository(Repository[User]):
    model = User

    # Add custom queries here, e.g.:
    async def find_by_email(self, email: str) -> User | None:
        return await self.first(email=email)
'''

def _users_schemas() -> str:
    return '''\
"""
Schemas for the Users module.

In Aura, schemas are the Spec — they define the contract of the API.
The framework derives validation, serialisation and OpenAPI docs from them.
"""
from __future__ import annotations

from aura import Schema


class CreateUserDTO(Schema):
    """Data required to create a new user."""
    name:  str
    email: str


class UpdateUserDTO(Schema):
    """Partial update — all fields optional."""
    name:  str | None = None
    email: str | None = None


class UserResponse(Schema):
    """What the API returns for a user."""
    id:    int
    name:  str
    email: str
'''

def _users_service() -> str:
    return '''\
"""UserService — business logic layer."""

from __future__ import annotations

from aura import injectable, NotFoundException, ConflictException, Log
from .models import User
from .repositories import UserRepository


@injectable
class UserService:
    """Handles all business logic for the Users feature."""

    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def list_users(self) -> list[User]:
        Log.info("Fetching all users from database")
        return await self.user_repository.list()

    async def get_user(self, user_id: int) -> User:
        Log.info("Fetching user", user_id=user_id)
        user = await self.user_repository.get(user_id)
        if user is None:
            raise NotFoundException(f"User {user_id} not found")
        return user

    async def create_user(self, data: CreateUserDTO) -> User:
        Log.info("Creating user in database", email=data.email)
        existing = await self.user_repository.first(email=data.email)
        if existing is not None:
            raise ConflictException(f"Email '{data.email}' already in use")
        return await self.user_repository.create(**data.model_dump())

    async def update_user(self, user_id: int, data: UpdateUserDTO) -> User:
        Log.info("Updating user in database", user_id=user_id)
        await self.get_user(user_id)
        return await self.user_repository.update(user_id, **data.model_dump(exclude_none=True))

    async def delete_user(self, user_id: int) -> None:
        Log.info("Deleting user from database", user_id=user_id)
        await self.get_user(user_id)
        await self.user_repository.delete(user_id)
'''

def _users_controller() -> str:
    return '''\
"""
UsersController — HTTP handlers for the Users module.

Route handlers are thin: they receive validated input, call the service,
and return the result. Business logic lives in UserService.
"""
from __future__ import annotations

from aura import get, post, put, delete, Body, Param, Log
from .schemas import CreateUserDTO, UpdateUserDTO, UserResponse
from .service import UserService


class UsersController:
    """Handles HTTP requests for /users routes."""

    def __init__(self, service: UserService) -> None:
        # UserService is injected automatically by the DI container
        self.service = service

    @get("/")
    async def list_users(self) -> list[UserResponse]:
        """List all users.
        
        Zero manual mapping boilerplate: returning User ORM model objects directly
        from the service is automatically mapped to UserResponse list DTOs!
        """
        Log.info("HTTP request to list users")
        return await self.service.list_users()



    @get("/interceptor")
    async def check_interceptor(self) -> dict:
        """Route demonstrating request log interception.
        
        This route shows how RequestLogInterceptor automatically captures
        incoming HTTP requests, extracts/generates unique request IDs, and
        associates them with logging contexts. Check your terminal logs!
        """
        return {
            "message": (
                "Request log interceptor is active. Check terminal console "
                "output for structured logging and request IDs!"
            ),
            "interceptor": "RequestLogInterceptor",
        }

    @get("/{user_id}")
    async def get_user(
        self,
        user_id: int,
    ) -> UserResponse:
        """Get a user by ID. Returns 404 if not found."""
        return await self.service.get_user(user_id)

    @post("/", status=201)
    async def create_user(
        self,
        body: Body[CreateUserDTO],
    ) -> UserResponse:
        """Create a new user. Returns 409 if email is already taken."""
        return await self.service.create_user(body)

    @put("/{user_id}")
    async def update_user(
        self,
        user_id: int,
        body:    Body[UpdateUserDTO],
    ) -> UserResponse:
        """Partially update a user."""
        return await self.service.update_user(user_id, body)

    @delete("/{user_id}", status=204)
    async def delete_user(
        self,
        user_id: int,
    ) -> None:
        """Delete a user. Returns 404 if not found."""
        await self.service.delete_user(user_id)
'''

def _users_module() -> str:
    return '''\
"""
UsersModule — encapsulates the entire Users feature.

@Module declares:
  providers   — classes the DI container can inject (services, repos, etc.)
  controllers — classes with route handlers
  prefix      — URL prefix for all routes in this module
  tags        — OpenAPI tag group
"""
from aura import Module
from .controller import UsersController
from .service import UserService
from .repositories import UserRepository


@Module(
    providers=[UserService, UserRepository],
    controllers=[UsersController],
    prefix="/users",
    tags=["Users"],
)
class UsersModule:
    pass
'''

def _users_init() -> str:
    return '"""Users module."""\n'

# ---- tests/ ----------------------------------------------------------------

def _conftest(project_name: str) -> str:
    return f'''\
"""Pytest fixtures for {project_name}."""
from __future__ import annotations

import os
import pytest

# Ensure we use an isolated in-memory SQLite database for all test cases
os.environ["AURA__DATABASE__URL"] = "sqlite+aiosqlite:///file:test_aura?mode=memory&cache=shared"

from aura.orm import db, AuraModel
from aura.testing.client import AuraTestClient
from main import app


@pytest.fixture(autouse=True)
async def setup_database():
    """Setup a clean database schema and seed mock data before each test."""
    if db._engine is None:
        db.init(os.environ["AURA__DATABASE__URL"])
    await db.create_all(AuraModel)

    # Seed initial test users
    async with db.session() as session:
        from modules.users.models import User
        session.add_all([
            User(id=1, name="Alice", email="alice@example.com"),
            User(id=2, name="Bob", email="bob@example.com"),
        ])
        await session.commit()

    yield

    await db.drop_all(AuraModel)


@pytest.fixture
async def client():
    """HTTP test client using native AuraTestClient."""
    async with AuraTestClient(app) as c:
        yield c
'''

def _test_users() -> str:
    return '''\
"""
Integration tests for the Users module.

These tests hit the real ASGI app (no mocking) and validate
the full request → controller → service → response pipeline.
"""
from __future__ import annotations

import pytest


async def test_list_users(client):
    """Seed data has 2 users — listing returns them."""
    r = await client.get("/users/")
    assert r.status_code == 200
    users = r.json()
    assert len(users) == 2
    assert users[0]["name"] == "Alice"


async def test_get_user(client):
    r = await client.get("/users/1")
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


async def test_get_user_not_found(client):
    r = await client.get("/users/999")
    assert r.status_code == 404


async def test_create_user(client):
    r = await client.post("/users/", json={"name": "Carol", "email": "carol@example.com"})
    assert r.status_code == 201
    data = r.json()
    assert data["id"] == 3
    assert data["name"] == "Carol"


async def test_create_user_duplicate_email(client):
    await client.post("/users/", json={"name": "X", "email": "dup@example.com"})
    r = await client.post("/users/", json={"name": "Y", "email": "dup@example.com"})
    assert r.status_code == 409


async def test_update_user(client):
    r = await client.put("/users/1", json={"name": "Alice Updated"})
    assert r.status_code == 200
    assert r.json()["name"] == "Alice Updated"
    assert r.json()["email"] == "alice@example.com"  # unchanged


async def test_delete_user(client):
    r = await client.delete("/users/1")
    assert r.status_code == 204

    r = await client.get("/users/1")
    assert r.status_code == 404


async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_user_factory_demo(client):
    """Demo showcasing how to generate users using the new Factory system."""
    from database.factories.user_factory import UserFactory

    # 1. Instanciar na memória síncronamente (rápido!)
    user = UserFactory().make(name="Jhone Doe")
    assert user.name == "Jhone Doe"
    assert user.id is None
'''

def _user_seeder_template() -> str:
    return '''\
"""User Model Seeder.

Generated by Aura CLI.
"""
from __future__ import annotations

from aura import Seeder, injectable
from modules.users.models import User
from ..factories import UserFactory


@injectable
class UserSeeder(Seeder):
    def __init__(self, factory: UserFactory) -> None:
        self.factory = factory

    async def run(self) -> None:
        # Create some default users using the factory.
        # We only override specific fields; the factory automatically fills in the rest.
        alice = self.factory.make(name="Alice")  # email will be filled automatically
        bob = self.factory.make(email="bob@example.com")  # name will be filled automatically

        await self.save(alice)
        await self.save(bob)

        # Option 2 (Alternative): Directly create and persist in a single step:
        # admin = await self.factory.create(name="Admin User", email="admin@example.com")
'''


def _database_seeder_template() -> str:
    return '''\
"""Main Database Seeder.

Generated by Aura CLI.
"""
from __future__ import annotations

from aura import Seeder, injectable
from database.seeders.user_seeder import UserSeeder


@injectable
class DatabaseSeeder(Seeder):
    async def run(self) -> None:
        # Executa seeders em ordem sequencial encadeada
        await self.call([
            UserSeeder,
        ])
'''


def _user_factory_template() -> str:
    return '''\
"""User Model Factory.

Generated by Aura CLI.
"""
from __future__ import annotations

from typing import Any

from aura.di import injectable
from aura.orm import Factory
from modules.users.models import User


@injectable
class UserFactory(Factory[User]):
    """Factory for generating User instances with realistic test data."""
    model = User

    def definition(self) -> dict[str, Any]:
        return {
            "name": lambda: self.faker.name(),
            "email": lambda: self.faker.unique.email(),
        }
'''


def _tests_init() -> str:
    return '"""Test suite."""\n'


def _factories_init() -> str:
    return '''\
"""Database factories package."""

from .user_factory import UserFactory

__all__ = ["UserFactory"]
'''


def _seeders_init() -> str:
    return '''\
"""Database seeders package."""

from .user_seeder import UserSeeder
from .database_seeder import DatabaseSeeder

__all__ = ["UserSeeder", "DatabaseSeeder"]
'''


# ---------------------------------------------------------------------------
# Build the file map
# ---------------------------------------------------------------------------

def _build_files(project_name: str) -> dict[str, str]:
    snake = _snake(project_name)
    return {
        "main.py":                        _main_py(project_name, snake),
        "aura.toml":                      _aura_toml(project_name, snake),
        "pyproject.toml":                 _pyproject_toml(project_name),
        ".env":                           _env_example(),
        ".env.example":                   _env_example(),
        "README.md":                      _readme(project_name),
        ".gitignore":                     _gitignore(),
        "modules/__init__.py":                 '"""Application modules."""\n',
        "modules/users/__init__.py":           _users_init(),
        "modules/users/models.py":             _users_models(),
        "modules/users/schemas.py":            _users_schemas(),
        "modules/users/repositories.py":       _users_repositories(),
        "modules/users/service.py":            _users_service(),
        "modules/users/controller.py":         _users_controller(),
        "modules/users/module.py":             _users_module(),
        "database/__init__.py":                '"""Database package."""\n',
        "database/seeders/__init__.py":        _seeders_init(),
        "database/seeders/user_seeder.py":     _user_seeder_template(),
        "database/seeders/database_seeder.py": _database_seeder_template(),
        "database/factories/__init__.py":      _factories_init(),
        "database/factories/user_factory.py":  _user_factory_template(),
        "tests/__init__.py":              _tests_init(),
        "tests/conftest.py":              _conftest(project_name),
        "tests/test_users.py":            _test_users(),
    }


# ---------------------------------------------------------------------------
# Command — accepts name directly: aura new my-project
# ---------------------------------------------------------------------------

@app.callback(invoke_without_command=True)
def new_project(
    ctx: typer.Context,
    project_name: str = typer.Argument(None, help="Name of the new project"),
    directory: str = typer.Option(".", "--dir", "-d", help="Parent directory"),
) -> None:
    """Scaffold a new Aura project with a working boilerplate.

    Creates a complete project structure with a working Users module,
    integration tests, and everything needed to run immediately.

    Examples::

        aura new my-api
        aura new blog --dir ~/projects
    """
    if ctx.invoked_subcommand is not None:
        return

    if not project_name:
        console.print(ctx.get_help())
        return

    snake = _snake(project_name)
    target = Path(directory).resolve() / snake

    if target.exists():
        console.print(f"[red]✗[/] Directory '[bold]{target}[/]' already exists.")
        raise typer.Exit(1)

    files = _build_files(project_name)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Scaffolding [bold cyan]{project_name}[/]...",
            total=len(files),
        )
        for rel_path, content in files.items():
            abs_path = target / rel_path
            abs_path.parent.mkdir(parents=True, exist_ok=True)
            abs_path.write_text(content, encoding="utf-8")
            progress.advance(task)

    console.print()
    console.print(
        Panel(
            f"[bold green]✓ Project created![/]\n\n"
            f"[bold]Next steps:[/]\n\n"
            f"  [cyan]cd {snake}[/]\n"
            f"  [cyan]pip install -e '.\\[dev]'[/]\n"
            f"  [cyan]aura db seed[/]\n"
            f"  [cyan]aura run --reload[/]\n\n"
            f"[dim]API docs →  http://localhost:8000/docs[/]\n"
            f"[dim]Health   →  http://localhost:8000/health[/]",
            title=f"[bold cyan]🌌 {project_name}[/]",
            expand=False,
        )
    )

"""Alembic integration helpers for Aura ORM migrations."""

from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path
from typing import Any

_SAFE_MODULE_PATH = re.compile(r"^[a-zA-Z_][\w]*(\.[a-zA-Z_][\w]*)*$")
_MODEL_SCAN_DIRS = ("modules", "database", "app", "src")


def _is_safe_module_path(module_path: str) -> bool:
    """Return True when *module_path* is a simple dotted Python module name."""
    return bool(_SAFE_MODULE_PATH.match(module_path))


def autoload_project_models(project_root: str | Path | None = None) -> list[str]:
    """Import model modules so :class:`~aura.orm.base.AuraModel` metadata is populated.

    Scans Aura project conventions (``modules/**/models.py``, ``database/models.py``,
    root ``models.py``) and imports ``main`` when present.  Used by generated
    Alembic ``env.py`` so ``migrate make --autogenerate`` sees all tables without
    manual imports.

    Args:
        project_root: Project directory (defaults to :func:`os.getcwd`).

    Returns:
        Dotted module paths successfully imported.
    """
    root = Path(project_root or os.getcwd()).resolve()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)

    loaded: list[str] = []

    def _try_import(module_path: str) -> None:
        if not _is_safe_module_path(module_path):
            return
        try:
            importlib.import_module(module_path)
        except Exception:
            return
        loaded.append(module_path)

    _try_import("main")

    for scan_dir in _MODEL_SCAN_DIRS:
        base = root / scan_dir
        if not base.is_dir():
            continue
        for models_file in base.rglob("models.py"):
            if any(part.startswith(".") or part == "__pycache__" for part in models_file.parts):
                continue
            rel_parent = models_file.parent.relative_to(root)
            module_path = ".".join(rel_parent.parts) + ".models"
            _try_import(module_path)

    root_models = root / "models.py"
    if root_models.is_file():
        _try_import("models")

    return loaded


def get_alembic_config(
    migrations_dir: str | Path = "migrations",
    database_url: str | None = None,
) -> Any:
    """Build and return an Alembic :class:`~alembic.config.Config` object.

    Args:
        migrations_dir: Path to the Alembic migrations directory.
        database_url: Override the ``sqlalchemy.url`` config option.
                      If ``None``, the value from ``alembic.ini`` is used.

    Returns:
        An Alembic Config instance ready for programmatic use.

    Raises:
        ImportError: If Alembic is not installed.
    """
    try:
        from alembic.config import Config
    except ImportError as exc:
        raise ImportError(
            "Alembic is required for migrations. "
            "Install with: pip install aura-framework[sqlalchemy]"
        ) from exc

    migrations_path = Path(migrations_dir).resolve()
    ini_file = migrations_path.parent / "alembic.ini"

    config = Config(str(ini_file) if ini_file.exists() else None)
    config.set_main_option("script_location", str(migrations_path))

    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)

    return config


def run_migrations_offline(target_metadata: Any, url: str) -> None:
    """Run migrations in 'offline' mode (generates SQL without a live connection).

    Intended to be called from the Alembic ``env.py`` file.

    Args:
        target_metadata: The SQLAlchemy metadata to migrate.
        url: The database URL.
    """
    try:
        from alembic import context as alembic_context
    except ImportError as exc:
        raise ImportError("Alembic not installed") from exc

    alembic_context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with alembic_context.begin_transaction():
        alembic_context.run_migrations()


async def run_migrations_online(target_metadata: Any, engine: Any) -> None:
    """Run migrations in 'online' mode using an async engine.

    Intended to be called from the Alembic ``env.py`` file.

    Args:
        target_metadata: The SQLAlchemy metadata to migrate.
        engine: An async SQLAlchemy engine.
    """
    try:
        from alembic import context as alembic_context
    except ImportError as exc:
        raise ImportError("Alembic / SQLAlchemy not installed") from exc

    async with engine.connect() as connection:
        await connection.run_sync(
            lambda sync_conn: alembic_context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
                render_as_batch=True,
            )
        )
        async with connection.begin():
            await connection.run_sync(lambda _: alembic_context.run_migrations())


def generate_env_py(migrations_dir: Path, model_import: str | None) -> str:
    """Generate the content for an Alembic ``env.py`` file.

    Args:
        migrations_dir: Directory where the file will be placed.
        model_import: Python import path to the application's AuraModel base,
                      e.g. ``"myapp.models:Base"``.  When ``None`` a commented
                      placeholder is inserted instead.

    Returns:
        String content for ``env.py``.
    """
    if model_import is not None:
        module, attr = model_import.split(":")
        import_block = (
            f"# Import your application's models so Alembic can detect schema changes.\n"
            f"from {module} import {attr} as target_metadata_base\n\n"
            f"target_metadata = target_metadata_base.metadata"
        )
    else:
        import_block = (
            "# Auto-register AuraModel subclasses (modules/**/models.py, database/models.py).\n"
            "from aura.orm import AuraModel\n"
            "from aura.orm.migrations import autoload_project_models\n\n"
            "autoload_project_models()\n"
            "target_metadata = AuraModel.metadata"
        )

    return f'''\
"""Alembic env.py - generated by Aura CLI."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from aura.orm.migrations import (
    run_migrations_offline as aura_offline,
    run_migrations_online as aura_online,
)

{import_block}

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    aura_offline(target_metadata, url)


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    engine = create_async_engine(url)
    try:
        asyncio.run(aura_online(target_metadata, engine))
    finally:
        asyncio.run(engine.dispose())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
'''

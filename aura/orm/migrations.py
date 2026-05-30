"""Alembic integration helpers for Aura ORM migrations."""

from __future__ import annotations

from pathlib import Path
from typing import Any


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
            "# Import AuraModel and attempt to import main to auto-register all models.\n"
            "from aura.orm import AuraModel\n"
            "try:\n"
            "    import main\n"
            "except ImportError:\n"
            "    pass\n\n"
            "# Dynamically import all modules' models to register them on AuraModel.metadata\n"
            "import os\n"
            "import importlib\n"
            "proj_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))\n"
            "modules_dir = os.path.join(proj_dir, 'modules')\n"
            "if os.path.exists(modules_dir):\n"
            "    for root, dirs, files in os.walk(modules_dir):\n"
            "        if 'models.py' in files:\n"
            "            rel_path = os.path.relpath(root, proj_dir)\n"
            "            import_path = f\"{rel_path.replace(os.sep, '.')}.models\"\n"
            "            try:\n"
            "                importlib.import_module(import_path)\n"
            "            except Exception:\n"
            "                pass\n\n"
            "target_metadata = AuraModel.metadata"
        )

    return f'''\
"""Alembic env.py — generated by Aura CLI."""
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

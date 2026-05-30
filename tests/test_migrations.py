"""Tests for Alembic integration and migration helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import MetaData

from aura.orm.migrations import (
    generate_env_py,
    get_alembic_config,
    run_migrations_offline,
    run_migrations_online,
)


def test_get_alembic_config_defaults() -> None:
    """Verifies that get_alembic_config correctly parses directories and URLs."""
    config = get_alembic_config(migrations_dir="tests/dummy_migrations", database_url="sqlite+aiosqlite:///:memory:")
    assert config.get_main_option("sqlalchemy.url") == "sqlite+aiosqlite:///:memory:"
    assert "tests/dummy_migrations" in config.get_main_option("script_location")


def test_generate_env_py_scaffold() -> None:
    """Verifies the content generated for env.py is correct and imports helpers."""
    content_no_model = generate_env_py(Path("migrations"), None)
    assert "from aura.orm.migrations import" in content_no_model
    assert "aura_offline" in content_no_model
    assert "aura_online" in content_no_model
    assert "target_metadata = AuraModel.metadata" in content_no_model

    content_with_model = generate_env_py(Path("migrations"), "app.models:Base")
    assert "from app.models import Base as target_metadata_base" in content_with_model


@patch("alembic.context")
def test_run_migrations_offline(mock_context: MagicMock) -> None:
    """Verifies that run_migrations_offline configures and executes offline migration runs."""
    metadata = MetaData()
    run_migrations_offline(metadata, "sqlite:///:memory:")

    mock_context.configure.assert_called_once_with(
        url="sqlite:///:memory:",
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    mock_context.begin_transaction.assert_called_once()
    mock_context.run_migrations.assert_called_once()



@pytest.mark.anyio
@patch("alembic.context")
async def test_run_migrations_online(mock_context: MagicMock) -> None:
    """Verifies that run_migrations_online executes online migrations.

    Runs them inside an async transaction.
    """
    metadata = MetaData()

    # Mock SQLAlchemy connection and transaction objects
    mock_transaction = MagicMock()

    mock_connection = MagicMock()
    mock_connection.begin = MagicMock(return_value=mock_transaction)

    # Mock synchronous run runner helper
    async def fake_run_sync(fn: Callable[..., Any]) -> Any:
        return fn(mock_connection)
    mock_connection.run_sync = fake_run_sync

    mock_engine = MagicMock()
    mock_engine.connect = MagicMock()

    # Setup async context managers
    class AsyncContextMock:
        async def __aenter__(self) -> Any:
            return mock_connection
        async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    class AsyncTxMock:
        async def __aenter__(self) -> Any:
            return mock_transaction
        async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            pass

    mock_engine.connect.return_value = AsyncContextMock()
    mock_connection.begin.return_value = AsyncTxMock()

    await run_migrations_online(metadata, mock_engine)

    mock_context.configure.assert_called_once_with(
        connection=mock_connection,
        target_metadata=metadata,
        render_as_batch=True,
    )
    mock_context.run_migrations.assert_called_once()


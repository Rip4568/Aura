"""Base configuration classes for the Aura framework."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from aura.logging.config import LogConfig


class ServerConfig(BaseSettings):
    """HTTP server configuration.

    Attributes:
        host: Bind address for the server.
        port: TCP port to listen on.
        workers: Number of worker processes.
        reload: Enable auto-reload on file changes (development only).
    """

    model_config = SettingsConfigDict(env_prefix="SERVER_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False


class DatabaseConfig(BaseSettings):
    """Database connection configuration.

    Attributes:
        url: SQLAlchemy async connection URL.
        pool_size: Number of connections maintained in the pool.
        max_overflow: Maximum connections above ``pool_size``.
        echo: Log all SQL statements (development only).
    """

    model_config = SettingsConfigDict(env_prefix="DATABASE_", extra="ignore")

    url: str = "sqlite+aiosqlite:///./aura.db"
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class JobsConfig(BaseSettings):
    """Background jobs / task queue configuration.

    Attributes:
        backend: Queue backend identifier (``memory``, ``saq``, ``taskiq``).
        broker_url: Broker connection URL (used when backend is not ``memory``).
        default_queue: Name of the default queue.
        max_workers: Maximum concurrent job workers.
    """

    model_config = SettingsConfigDict(env_prefix="JOBS_", extra="ignore")

    backend: str = "memory"
    broker_url: str = "redis://localhost:6379"
    default_queue: str = "default"
    max_workers: int = 4


class AuraConfig(BaseSettings):
    """
    Top-level application configuration.

    Settings are loaded from environment variables and/or a ``.env`` file.
    Nested settings are separated by ``__`` (double underscore).

    Example ``.env``::

        APP_NAME="My API"
        DEBUG=true
        SECRET_KEY="supersecretkey123456789012345678"
        SERVER__PORT=9000
        DATABASE__URL="postgresql+asyncpg://user:pass@localhost/mydb"

    Attributes:
        app_name: Human-readable application name.
        debug: Enable debug mode (verbose errors, auto-reload, etc.).
        secret_key: Secret key used for signing tokens and sessions.
        server: :class:`ServerConfig` nested config.
        database: :class:`DatabaseConfig` nested config.
        jobs: :class:`JobsConfig` nested config.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Aura App"
    debug: bool = False
    secret_key: str = Field(default="change-me-in-production-32chars!!", min_length=32)

    server: ServerConfig = ServerConfig()
    database: DatabaseConfig = DatabaseConfig()
    jobs: JobsConfig = JobsConfig()
    logging: LogConfig = Field(default_factory=LogConfig)

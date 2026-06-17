"""Task queue backend implementations."""

from __future__ import annotations

from typing import Any

from aura.jobs.backends.base import TaskBackend
from aura.jobs.backends.memory import MemoryBackend

__all__ = ["TaskBackend", "MemoryBackend", "DatabaseBackend"]


def __getattr__(name: str) -> Any:
    if name == "DatabaseBackend":
        from aura.jobs.backends.database import DatabaseBackend

        return DatabaseBackend
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

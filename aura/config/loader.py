"""Configuration loader utilities."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypeVar

from aura.config.base import AuraConfig

C = TypeVar("C", bound=AuraConfig)


def load_config(
    config_class: type[C] = AuraConfig,  # type: ignore[assignment]
    env_file: str | Path | None = None,
) -> C:
    """Instantiate a config class, optionally overriding the env file path.

    Args:
        config_class: A subclass of :class:`~aura.config.base.AuraConfig`
            to instantiate.  Defaults to :class:`~aura.config.base.AuraConfig`.
        env_file: Path to a ``.env`` file.  When provided it overrides the
            ``env_file`` field of the model's ``SettingsConfigDict``.

    Returns:
        A fully-populated config instance.
    """
    if env_file is not None:
        # Override env_file at instantiation time via ``_env_file``
        return config_class(_env_file=str(env_file))  # type: ignore[call-arg]
    return config_class()


def get_env(key: str, default: str = "") -> str:
    """Retrieve an environment variable with an optional default.

    Args:
        key: The environment variable name.
        default: Value to return when the variable is not set.

    Returns:
        The environment variable value or *default*.
    """
    return os.environ.get(key, default)

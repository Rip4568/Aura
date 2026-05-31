"""Dependency Injection module."""

from aura.di.container import DIContainer, Lifetime, container
from aura.di.decorators import inject, injectable
from aura.di.providers import Provider, ScopedProvider, SingletonProvider, TransientProvider

__all__ = [
    "DIContainer",
    "Lifetime",
    "container",
    "injectable",
    "inject",
    "Provider",
    "SingletonProvider",
    "TransientProvider",
    "ScopedProvider",
]

"""Tests for aura.modules module."""

from __future__ import annotations

import pytest

from aura.di.container import DIContainer
from aura.di.decorators import injectable
from aura.modules.base import Module, ModuleMetadata
from aura.modules.registry import ModuleRegistry
from aura.routing.decorators import get

# ---------------------------------------------------------------------------
# Module decorator tests
# ---------------------------------------------------------------------------


def test_module_decorator_attaches_metadata() -> None:
    @Module(prefix="/users")
    class UserModule:
        pass

    assert hasattr(UserModule, "__aura_module__")
    meta = UserModule.__aura_module__
    assert isinstance(meta, ModuleMetadata)
    assert meta.prefix == "/users"


def test_module_decorator_default_values() -> None:
    @Module()
    class EmptyModule:
        pass

    meta = EmptyModule.__aura_module__
    assert meta.imports == []
    assert meta.providers == []
    assert meta.controllers == []
    assert meta.exports == []
    assert meta.prefix == ""
    assert meta.tags == []
    assert meta.guards == []


def test_module_with_controllers_and_providers() -> None:
    @injectable()
    class UserService:
        pass

    class UserController:
        @get("/users")
        async def list_users(self) -> None:
            pass

    @Module(controllers=[UserController], providers=[UserService])
    class UserModule:
        pass

    meta = UserModule.__aura_module__
    assert UserController in meta.controllers
    assert UserService in meta.providers


# ---------------------------------------------------------------------------
# ModuleRegistry tests
# ---------------------------------------------------------------------------


def test_registry_register_module() -> None:
    @Module()
    class AppModule:
        pass

    container = DIContainer()
    registry = ModuleRegistry(container)
    registry.register(AppModule)

    assert AppModule in registry._registered


def test_registry_non_module_raises() -> None:
    container = DIContainer()
    registry = ModuleRegistry(container)

    class NotAModule:
        pass

    with pytest.raises(TypeError, match="not an Aura module"):
        registry.register(NotAModule)


def test_registry_collects_routes() -> None:
    class UserController:
        @get("/")
        async def index(self) -> None:
            pass

    @Module(controllers=[UserController], prefix="/users")
    class UserModule:
        pass

    container = DIContainer()
    registry = ModuleRegistry(container)
    registry.register(UserModule)

    routes = registry.collect_routes()
    paths = {str(r.path) for r in routes}
    assert "/users/" in paths


def test_registry_registers_providers_in_container() -> None:
    @injectable()
    class MyService:
        pass

    @Module(providers=[MyService])
    class AppModule:
        pass

    container = DIContainer()
    registry = ModuleRegistry(container)
    registry.register(AppModule)

    assert container.is_registered(MyService)


def test_registry_handles_module_imports() -> None:
    @injectable()
    class SharedService:
        pass

    @Module(providers=[SharedService], exports=[SharedService])
    class SharedModule:
        pass

    @Module(imports=[SharedModule])
    class AppModule:
        pass

    container = DIContainer()
    registry = ModuleRegistry(container)
    registry.register(AppModule)

    # SharedModule should be registered transitively
    assert SharedModule in registry._registered
    assert container.is_registered(SharedService)

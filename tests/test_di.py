"""Tests for aura.di module."""

from __future__ import annotations

import pytest

from aura.di.container import DIContainer, Lifetime
from aura.di.decorators import injectable

# ---------------------------------------------------------------------------
# Test services
# ---------------------------------------------------------------------------


class Logger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)


class UserRepository:
    def __init__(self) -> None:
        self.users: list[dict] = []

    def add(self, user: dict) -> None:
        self.users.append(user)


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def create(self, name: str) -> dict:
        user = {"name": name}
        self.repo.add(user)
        return user


# ---------------------------------------------------------------------------
# Container tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_and_resolve_singleton() -> None:
    container = DIContainer()
    container.register(Logger)

    logger1 = await container.resolve(Logger)
    logger2 = await container.resolve(Logger)

    assert logger1 is logger2  # same singleton


@pytest.mark.asyncio
async def test_register_and_resolve_transient() -> None:
    container = DIContainer()
    container.register(Logger, lifetime=Lifetime.TRANSIENT)

    logger1 = await container.resolve(Logger)
    logger2 = await container.resolve(Logger)

    assert logger1 is not logger2  # different instances


@pytest.mark.asyncio
async def test_resolve_unregistered_raises() -> None:
    container = DIContainer()
    with pytest.raises(KeyError, match="UserRepository"):
        await container.resolve(UserRepository)


@pytest.mark.asyncio
async def test_resolve_optional_returns_none() -> None:
    container = DIContainer()
    result = await container.resolve_optional(Logger)
    assert result is None


@pytest.mark.asyncio
async def test_register_instance() -> None:
    container = DIContainer()
    repo = UserRepository()
    container.register_instance(UserRepository, repo)

    resolved = await container.resolve(UserRepository)
    assert resolved is repo


@pytest.mark.asyncio
async def test_register_factory() -> None:
    container = DIContainer()
    call_count = 0

    def factory() -> Logger:
        nonlocal call_count
        call_count += 1
        return Logger()

    container.register_factory(Logger, factory=factory, lifetime=Lifetime.TRANSIENT)

    await container.resolve(Logger)
    await container.resolve(Logger)
    assert call_count == 2


@pytest.mark.asyncio
async def test_is_registered() -> None:
    container = DIContainer()
    assert not container.is_registered(Logger)
    container.register(Logger)
    assert container.is_registered(Logger)


@pytest.mark.asyncio
async def test_auto_resolve_dependencies() -> None:
    container = DIContainer()
    container.register(UserRepository)
    container.register(UserService)

    service = await container.resolve(UserService)
    assert service.repo is await container.resolve(UserRepository)


@pytest.mark.asyncio
async def test_create_scope() -> None:
    container = DIContainer()
    container.register(Logger)

    child = container.create_scope()
    assert child.is_registered(Logger)

    # Child shares the same provider, so singleton is shared
    parent_logger = await container.resolve(Logger)
    child_logger = await child.resolve(Logger)
    assert parent_logger is child_logger


# ---------------------------------------------------------------------------
# injectable decorator tests
# ---------------------------------------------------------------------------


def test_injectable_decorator_marks_class() -> None:
    @injectable()
    class MyService:
        pass

    assert hasattr(MyService, "__aura_injectable__")
    assert MyService.__aura_injectable__["lifetime"] == Lifetime.SINGLETON


def test_injectable_decorator_custom_lifetime() -> None:
    @injectable(lifetime=Lifetime.TRANSIENT)
    class MyService:
        pass

    assert MyService.__aura_injectable__["lifetime"] == Lifetime.TRANSIENT

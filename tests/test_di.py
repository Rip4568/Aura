"""Tests for aura.di module."""

from typing import Annotated, Any, cast

import pytest

from aura.di.container import DIContainer, Lifetime
from aura.di.decorators import inject, injectable

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
        self.users: list[dict[str, Any]] = []

    def add(self, user: dict[str, Any]) -> None:
        self.users.append(user)


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def create(self, name: str) -> dict[str, Any]:
        user = {"name": name}
        self.repo.add(user)
        return user


class Database:
    def __init__(self) -> None:
        self.connected = False


class ServiceWithOptionalDep:
    def __init__(self, logger: Logger | None = None) -> None:
        self.logger = logger


class ServiceA:
    def __init__(self, service_b: "ServiceB") -> None:
        self.service_b = service_b


class ServiceB:
    def __init__(self, service_a: ServiceA) -> None:
        self.service_a = service_a


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
    assert cast(Any, MyService).__aura_injectable__["lifetime"] == Lifetime.SINGLETON


def test_injectable_decorator_custom_lifetime() -> None:
    @injectable(lifetime=Lifetime.TRANSIENT)
    class MyService:
        pass

    assert cast(Any, MyService).__aura_injectable__["lifetime"] == Lifetime.TRANSIENT


# ---------------------------------------------------------------------------
# F-04: Missing required dependency and circular dependency tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_required_dependency_raises() -> None:
    """Test that a service depending on an unregistered type raises RuntimeError."""

    class ServiceNeedingDb:
        def __init__(self, db: Database) -> None:
            self.db = db

    container = DIContainer()
    container.register(ServiceNeedingDb)

    # Attempting to resolve should raise RuntimeError with clear message
    with pytest.raises(
        RuntimeError,
        match="'ServiceNeedingDb' depends on 'Database' which is not registered",
    ):
        await container.resolve(ServiceNeedingDb)


@pytest.mark.asyncio
async def test_optional_missing_dependency_allowed() -> None:
    """Test that optional dependencies can be missing."""
    container = DIContainer()
    container.register(ServiceWithOptionalDep)

    service = await container.resolve(ServiceWithOptionalDep)
    assert service.logger is None


@pytest.mark.asyncio
async def test_circular_dependency_detection() -> None:
    """Test that circular dependencies are detected and raise RuntimeError."""
    container = DIContainer()
    container.register(ServiceA)
    container.register(ServiceB)

    # Attempting to resolve either service should raise RuntimeError about circular dependency
    with pytest.raises(RuntimeError, match="Circular dependency detected"):
        await container.resolve(ServiceA)


# ---------------------------------------------------------------------------
# F-05: Scoped provider memory and reuse tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scoped_instances_isolated_per_scope() -> None:
    """Test that scoped instances are isolated between different scopes."""
    container = DIContainer()
    container.register(Logger, lifetime=Lifetime.SCOPED)

    # Get instance from parent container
    parent_logger = await container.resolve(Logger)
    parent_logger.log("parent message")

    # Create child scope
    child = container.create_scope()
    child_logger = await child.resolve(Logger)

    # Scoped instances should be different
    assert parent_logger is not child_logger
    assert parent_logger.messages == ["parent message"]
    assert child_logger.messages == []


@pytest.mark.asyncio
async def test_scoped_cache_reused_within_scope() -> None:
    """Test that scoped cache is reused within the same scope."""
    container = DIContainer()
    container.register(Logger, lifetime=Lifetime.SCOPED)

    # Resolve same service twice
    logger1 = await container.resolve(Logger)
    logger2 = await container.resolve(Logger)

    # Should be same instance within scope
    assert logger1 is logger2


@pytest.mark.asyncio
async def test_scoped_cache_does_not_leak_across_containers() -> None:
    """Test that scoped cache doesn't leak when a container is garbage collected."""
    container = DIContainer()
    container.register(Logger, lifetime=Lifetime.SCOPED)

    # Create first scope and get logger
    scope1 = container.create_scope()
    logger1 = await scope1.resolve(Logger)

    # Create second scope
    scope2 = container.create_scope()
    logger2 = await scope2.resolve(Logger)

    # Instances should be different (different scopes)
    assert logger1 is not logger2


@pytest.mark.asyncio
async def test_container_startup_warms_singletons() -> None:
    """Test that startup() eagerly instantiates singleton providers."""
    container = DIContainer()
    instantiation_count = 0

    class CountingService:
        def __init__(self) -> None:
            nonlocal instantiation_count
            instantiation_count += 1

    container.register(CountingService, lifetime=Lifetime.SINGLETON)

    # Before startup, nothing should be instantiated
    assert instantiation_count == 0

    # After startup, singleton should be instantiated
    await container.startup()
    assert instantiation_count == 1

    # Resolving again should return the same instance
    await container.resolve(CountingService)
    assert instantiation_count == 1


@pytest.mark.asyncio
async def test_container_startup_continues_on_factory_error() -> None:
    """Test that startup() continues even if a factory raises an exception."""

    class FailingService:
        def __init__(self) -> None:
            raise RuntimeError("Factory error")

    class WorkingService:
        pass

    container = DIContainer()
    container.register(FailingService, lifetime=Lifetime.SINGLETON)
    container.register(WorkingService, lifetime=Lifetime.SINGLETON)

    # Should not raise, just log the error
    await container.startup()

    # WorkingService should still be available
    working = await container.resolve(WorkingService)
    assert working is not None


@pytest.mark.asyncio
async def test_container_shutdown_does_not_raise() -> None:
    """Test that shutdown() completes without error."""
    container = DIContainer()
    container.register(Logger)

    # Should not raise
    await container.shutdown()


@pytest.mark.asyncio
async def test_inject_marker_resolves_dependency() -> None:
    """Annotated[T, inject()] should resolve T from the container."""

    @injectable()
    class Repo:
        pass

    class Service:
        def __init__(self, repo: Annotated[Repo, inject()]) -> None:
            self.repo = repo

    container = DIContainer()
    container.register(Repo)
    container.register(Service)

    service = await container.resolve(Service)
    assert service.repo is await container.resolve(Repo)

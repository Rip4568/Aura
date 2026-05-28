"""DI decorators for the Aura framework."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, overload

from aura.di.container import Lifetime

T = TypeVar("T")


@overload
def injectable(_cls: type[T], *, lifetime: Lifetime = ...) -> type[T]: ...
@overload
def injectable(_cls: None = ..., *, lifetime: Lifetime = ...) -> Callable[[type[T]], type[T]]: ...
def injectable(
    _cls: type[T] | None = None,
    *,
    lifetime: Lifetime = Lifetime.SINGLETON,
) -> type[T] | Callable[[type[T]], type[T]]:
    """
    Class decorator that marks a class as injectable by the DI container.

    Can be used with or without parentheses::

        @injectable
        class UserService: ...

        @injectable(lifetime=Lifetime.SCOPED)
        class UserRepository: ...

    Args:
        _cls: The class being decorated (set automatically when used without
            parentheses as ``@injectable``).
        lifetime: How long the instance should live.  Defaults to
            :attr:`~aura.di.container.Lifetime.SINGLETON`.

    Returns:
        The original class, unchanged except for the ``__aura_injectable__``
        attribute set on it.
    """

    def decorator(cls: type[T]) -> type[T]:
        cls.__aura_injectable__ = {  # type: ignore[attr-defined]
            "lifetime": lifetime,
        }
        return cls

    # Used as @injectable (no parentheses)
    if _cls is not None:
        return decorator(_cls)

    # Used as @injectable(...) (with parentheses)
    return decorator


class InjectMarker:
    """Marker attached to a parameter via ``Annotated`` metadata."""

    def __init__(self, name: str | None) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"InjectMarker(name={self.name!r})"


def inject(param_name: str | None = None) -> InjectMarker:
    """
    Parameter annotation helper for explicit dependency injection.

    In most cases Aura resolves dependencies automatically from type hints,
    so ``@inject`` is optional.  Use it when you need to override the
    resolved type or provide additional metadata.

    Args:
        param_name: When provided, resolve the dependency registered under
            this name instead of the parameter's type annotation.

    Returns:
        A descriptor/marker object that the container inspects at resolution
        time.

    Example::

        class UserService:
            def __init__(
                self,
                repo: Annotated[UserRepository, inject()],
            ) -> None:
                self.repo = repo
    """
    return InjectMarker(param_name)

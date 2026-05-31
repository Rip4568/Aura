"""Factories and Faker support for Aura ORM."""

from __future__ import annotations

import inspect
from typing import Any, Generic, TypeVar

from faker import Faker

from aura.di import injectable
from aura.orm.base import AuraModel
from aura.orm.session import current_session, db

ModelT = TypeVar("ModelT", bound=AuraModel)


class SubFactory:
    """Represents a foreign key or relationship between factories."""

    def __init__(self, factory_class: type[Factory[Any]], **overrides: Any) -> None:
        self.factory_class = factory_class
        self.overrides = overrides

    def make(self, **overrides: Any) -> Any:
        """Resolve this sub-factory by generating a model instance in memory."""
        factory = self.factory_class()
        merged = {**self.overrides, **overrides}
        return factory.make(**merged)

    async def create(self, **overrides: Any) -> Any:
        """Resolve this sub-factory by creating and persisting a model instance."""
        factory = self.factory_class()
        merged = {**self.overrides, **overrides}
        return await factory.create(**merged)


@injectable
class Factory(Generic[ModelT]):
    """Base factory class for generating and persisting Aura models."""

    faker: Faker = Faker()
    model: type[Any] | None = None

    def __init__(self, **overrides: Any) -> None:
        self._overrides: dict[str, Any] = overrides

    def definition(self) -> dict[str, Any]:
        """Define the default attributes for the factory."""
        raise NotImplementedError("Factories must implement the definition() method.")

    def get_model_class(self) -> type[ModelT]:
        """Retrieve the model class associated with this factory."""
        if self.model is not None:
            return self.model

        for base in getattr(self.__class__, "__orig_bases__", []):
            if hasattr(base, "__args__") and base.__args__:
                for arg in base.__args__:
                    if isinstance(arg, type) and issubclass(arg, AuraModel):
                        return arg  # type: ignore[return-value]

        raise AttributeError(
            f"Factory {self.__class__.__name__} must define a 'model' attribute "
            "or have a valid ModelT generic parameter."
        )

    def state(self, **attrs: Any) -> Factory[ModelT]:
        """Return a new factory instance with the accumulated overrides."""
        new_overrides = {**self._overrides, **attrs}
        return self.__class__(**new_overrides)

    def make(self, **overrides: Any) -> ModelT:
        """Instantiate the model in memory without saving to the database."""
        model_class = self.get_model_class()
        raw_attrs = {**self.definition(), **self._overrides, **overrides}

        resolved_attrs: dict[str, Any] = {}
        for key, value in raw_attrs.items():
            if isinstance(value, SubFactory):
                resolved_attrs[key] = value.make()
            elif callable(value) and not isinstance(value, type):
                resolved_attrs[key] = value()
            else:
                resolved_attrs[key] = value

        return model_class(**resolved_attrs)

    def make_many(self, count: int, **overrides: Any) -> list[ModelT]:
        """Create a list of model instances in memory."""
        return [self.make(**overrides) for _ in range(count)]

    async def _resolve_create_attrs(self, **overrides: Any) -> dict[str, Any]:
        """Resolve attributes recursively calling create() for sub-factories."""
        raw_attrs = {**self.definition(), **self._overrides, **overrides}
        resolved_attrs: dict[str, Any] = {}
        for key, value in raw_attrs.items():
            if isinstance(value, SubFactory):
                resolved_attrs[key] = await value.create()
            elif callable(value) and not isinstance(value, type):
                val = value()
                if inspect.isawaitable(val):
                    resolved_attrs[key] = await val
                else:
                    resolved_attrs[key] = val
            else:
                resolved_attrs[key] = value
        return resolved_attrs

    async def create(self, **overrides: Any) -> ModelT:
        """Instantiate and persist the model in the database."""
        session = current_session.get()
        if session is not None:
            resolved_attrs = await self._resolve_create_attrs(**overrides)
            instance = self.get_model_class()(**resolved_attrs)
            session.add(instance)
            await session.flush()
            return instance

        async with db.session() as session:
            token = current_session.set(session)
            try:
                resolved_attrs = await self._resolve_create_attrs(**overrides)
                instance = self.get_model_class()(**resolved_attrs)
                session.add(instance)
                await session.flush()
                await session.commit()
                await session.refresh(instance)
                return instance
            finally:
                current_session.reset(token)

    async def create_many(self, count: int, **overrides: Any) -> list[ModelT]:
        """Create a batch of model instances in the database."""
        session = current_session.get()
        if session is not None:
            return [await self.create(**overrides) for _ in range(count)]

        async with db.session() as session:
            token = current_session.set(session)
            try:
                results: list[ModelT] = []
                for _ in range(count):
                    inst = await self.create(**overrides)
                    results.append(inst)
                await session.commit()
                for inst in results:
                    await session.refresh(inst)
                return results
            finally:
                current_session.reset(token)

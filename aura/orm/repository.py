"""Generic async repository providing CRUD operations for AuraModel subclasses."""

from __future__ import annotations

import builtins
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aura.orm.base import AuraModel

ModelT = TypeVar("ModelT", bound=AuraModel)
T = TypeVar("T")


@dataclass
class Page(Generic[T]):
    """Result of a paginated query."""

    items: builtins.list[T]
    total: int
    page: int
    per_page: int
    has_next: bool


class Repository(Generic[ModelT]):
    """Generic async repository for CRUD operations.

    Subclass and set the ``model`` class attribute to get a fully functional
    repository bound to that model.

    Args:
        session: An active :class:`~sqlalchemy.ext.asyncio.AsyncSession`.

    Usage::

        class UserRepository(Repository[User]):
            model = User

    The session is **not** injected by the DI container — you must
    obtain one from :data:`~aura.orm.database.db` and pass it
    explicitly.  The recommended pattern inside a service is::

        from aura.orm.database import db

        @injectable
        class UserService:
            async def find(self, user_id: int) -> User:
                async with db.session() as session:
                    return await UserRepository(session).get_or_raise(user_id)

            async def list_active(self) -> list[User]:
                async with db.session() as session:
                    return await UserRepository(session).list(active=True)

    The ``async with db.session()`` block automatically commits on
    success and rolls back on any exception.

    .. note::

        Constructor-based ``AsyncSession`` injection
        (``def __init__(self, session: AsyncSession)``) requires a
        request-scoped DI container that is not yet implemented.
        Track progress at
        https://github.com/jonathasdavidd/Aura/issues.
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: int) -> ModelT | None:
        """Fetch a single record by primary key.

        Args:
            id: The primary-key value to look up.

        Returns:
            The model instance, or ``None`` if not found.
        """
        return await self.session.get(self.model, id)

    async def get_or_raise(self, id: int) -> ModelT:
        """Fetch a single record by primary key, raising 404 if absent.

        Args:
            id: The primary-key value to look up.

        Returns:
            The model instance.

        Raises:
            NotFoundException: If no record with the given id exists.
        """
        obj = await self.get(id)
        if obj is None:
            from aura.exceptions.http import NotFoundException
            raise NotFoundException(f"{self.model.__name__} with id {id} not found")
        return obj

    async def list(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        **filters: Any,
    ) -> list[ModelT]:
        """Fetch a paginated list of records with optional column filters.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            order_by: Column name to order by (ascending).
            **filters: Keyword arguments used as equality filters
                       (e.g. ``active=True``).

        Returns:
            A list of model instances.
        """
        stmt = select(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        if order_by:
            stmt = stmt.order_by(getattr(self.model, order_by))
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **data: Any) -> ModelT:
        """Insert a new record and return it.

        Args:
            **data: Column values to set on the new record.

        Returns:
            The newly created model instance (with id and timestamps populated).
        """
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, id: int, **data: Any) -> ModelT:
        """Update an existing record in place.

        Args:
            id: Primary-key of the record to update.
            **data: Columns to update and their new values.

        Returns:
            The updated model instance.

        Raises:
            NotFoundException: If no record with the given id exists.
        """
        obj = await self.get_or_raise(id)
        for key, value in data.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> bool:
        """Delete a record by primary key.

        Args:
            id: Primary-key of the record to delete.

        Returns:
            ``True`` if the record was deleted, ``False`` if not found.
        """
        obj = await self.get(id)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def exists(self, **filters: Any) -> bool:
        """Check whether at least one matching record exists.

        Args:
            **filters: Equality filters (column=value).

        Returns:
            ``True`` if a matching record exists.
        """
        stmt = select(self.model.id)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar() is not None

    async def count(self, **filters: Any) -> int:
        """Count records matching the given filters.

        Args:
            **filters: Equality filters (column=value).

        Returns:
            Number of matching records.
        """
        stmt = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def first(self, **filters: Any) -> ModelT | None:
        """Return the first record matching the given filters.

        Args:
            **filters: Equality filters (column=value).

        Returns:
            The first matching model instance, or ``None``.
        """
        stmt = select(self.model).limit(1)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def bulk_create(self, items: builtins.list[dict[str, Any]]) -> builtins.list[ModelT]:
        """Insert multiple records in a single flush.

        Args:
            items: List of dicts, each containing column-value pairs.

        Returns:
            List of newly created model instances.
        """
        objects = [self.model(**item) for item in items]
        self.session.add_all(objects)
        await self.session.flush()
        for obj in objects:
            await self.session.refresh(obj)
        return objects

    async def bulk_update(
        self,
        ids: builtins.list[int],
        **data: Any,
    ) -> builtins.list[ModelT]:
        """Update the same set of fields on multiple records at once.

        Args:
            ids: Primary-key values of the records to update.
            **data: Column values to set on every matched record.

        Returns:
            List of updated model instances (same order as *ids*).

        Raises:
            NotFoundException: If any id in *ids* does not exist.
        """
        objects = []
        for pk in ids:
            obj = await self.get_or_raise(pk)
            for key, value in data.items():
                setattr(obj, key, value)
            objects.append(obj)
        await self.session.flush()
        for obj in objects:
            await self.session.refresh(obj)
        return objects

    async def bulk_delete(self, ids: builtins.list[int]) -> int:
        """Delete multiple records by primary key in a single flush.

        Args:
            ids: Primary-key values of the records to delete.

        Returns:
            Number of records actually deleted (skips missing ids).
        """
        deleted = 0
        for pk in ids:
            obj = await self.get(pk)
            if obj is not None:
                await self.session.delete(obj)
                deleted += 1
        await self.session.flush()
        return deleted

    async def paginate(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        order_by: str | None = None,
        **filters: Any,
    ) -> Page[ModelT]:
        # count query with filters applied
        count_stmt = select(func.count()).select_from(self.model)
        for key, value in filters.items():
            count_stmt = count_stmt.where(getattr(self.model, key) == value)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # data query with filters, ordering, and pagination
        offset = (page - 1) * per_page
        stmt = select(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        if order_by:
            stmt = stmt.order_by(getattr(self.model, order_by))
        stmt = stmt.limit(per_page).offset(offset)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return Page(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            has_next=page * per_page < total,
        )

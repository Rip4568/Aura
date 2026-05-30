"""Generic async repository providing CRUD operations for AuraModel subclasses."""

from __future__ import annotations

import uuid

# ruff: noqa: UP006, UP035
from dataclasses import dataclass
from typing import Any, Generic, List, TypeAlias, TypeVar, cast

from sqlalchemy import func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from aura.orm.base import AuraModel

ModelT = TypeVar("ModelT", bound=AuraModel)
T = TypeVar("T")

PkType: TypeAlias = int | str | uuid.UUID


@dataclass
class Page(Generic[T]):
    """Result of a paginated query."""

    items: List[T]
    total: int
    page: int
    per_page: int
    has_next: bool


def _apply_filters(stmt: Any, model: type, filters: dict[str, Any]) -> Any:
    """Apply equality filters to a SQLAlchemy statement.

    Args:
        stmt: The base SELECT/COUNT statement.
        model: The AuraModel subclass being queried.
        filters: Column name → value pairs for WHERE clauses.

    Returns:
        The statement with WHERE clauses applied.

    Raises:
        UnprocessableEntityException: If a filter key has no matching column.
    """
    for key, value in filters.items():
        col = getattr(model, key, None)
        if col is None:
            from aura.exceptions.http import UnprocessableEntityException
            raise UnprocessableEntityException(f"Unknown filter field: '{key}'")
        stmt = stmt.where(col == value)
    return stmt


def _apply_order_by(stmt: Any, model: type, order_by: str) -> Any:
    """Apply ordering to a SQLAlchemy statement.

    Prefix the column name with ``-`` for descending order.

    Args:
        stmt: The SELECT statement.
        model: The AuraModel subclass.
        order_by: Column name, optionally prefixed with ``-`` for DESC.

    Returns:
        The statement with ORDER BY applied.
    """
    descending = order_by.startswith("-")
    col_name = order_by.lstrip("-")
    col = getattr(model, col_name, None)
    if col is None:
        from aura.exceptions.http import UnprocessableEntityException
        raise UnprocessableEntityException(f"Unknown order_by field: '{col_name}'")
    return stmt.order_by(col.desc() if descending else col)


class Repository(Generic[ModelT]):
    """Generic async repository for CRUD operations.

    Subclass and set the ``model`` class attribute to get a fully functional
    repository bound to that model.

    Args:
        session: An active :class:`~sqlalchemy.ext.asyncio.AsyncSession`.

    Usage::

        class UserRepository(Repository[User]):
            model = User

    The repository supports two powerful, boilerplate-free injection paradigms:

    1. **Dynamic Context Propagation (Default / Recommended)**:
       When registered as a ``Lifetime.SINGLETON`` (the default), the repository
       dynamically resolves the active request's transactional session from the
       context-local async environment (via ``ContextVar``). This allows you to
       use simple, clean constructor-based injection without manual sessions:

       .. code-block:: python

           @injectable
           class UserRepository(Repository[User]):
               model = User

           @injectable
           class UserService:
               def __init__(self, repo: UserRepository) -> None:
                   self.repo = repo  # Injetado como Singleton pelo container

               async def find(self, user_id: int) -> User:
                   # Pura lógica de negócios! A transação é gerenciada
                   # automaticamente pelo DatabaseMiddleware.
                   return await self.repo.get_or_raise(user_id)

    2. **Request-Scoped Constructor Injection**:
       If you prefer to have the database session injected directly into your constructor
       by the DI container, you can register the repository (and service) as ``Lifetime.SCOPED``.
       The request's scoped container will automatically inject the active ``AsyncSession``:

       .. code-block:: python

           @injectable(lifetime=Lifetime.SCOPED)
           class UserRepository(Repository[User]):
               model = User
               def __init__(self, session: AsyncSession) -> None:
                   super().__init__(session)

    For running commands, scripts, or background workers outside the HTTP lifecycle,
    manually manage the session boundary using ``db.session()``::

        async with db.session() as session:
            # Passa a sessão isolada para o construtor do repositório
            repo = UserRepository(session)
            await repo.create(title="CLI Task", active=True)
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        if self._session is not None:
            return self._session

        from aura.orm.session import current_session
        sess = current_session.get()
        if sess is None:
            raise RuntimeError(
                "Repository: No active database session found in current context "
                f"for '{self.__class__.__name__}'. "
                "Ensure DatabaseMiddleware is active in your application, or pass a session "
                "explicitly to the constructor: UserRepository(session)."
            )
        return sess

    async def get(self, id: PkType) -> ModelT | None:
        """Fetch a single record by primary key.

        Args:
            id: The primary-key value to look up.

        Returns:
            The model instance, or ``None`` if not found.
        """
        return await self.session.get(self.model, id)

    async def get_or_raise(self, id: PkType) -> ModelT:
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
    ) -> List[ModelT]:
        """Fetch a paginated list of records with optional column filters.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.
            order_by: Column name to order by; prefix with ``-`` for DESC.
            **filters: Keyword arguments used as equality filters
                       (e.g. ``active=True``).

        Returns:
            A list of model instances.
        """
        stmt = select(self.model)
        stmt = _apply_filters(stmt, self.model, filters)
        if order_by:
            stmt = _apply_order_by(stmt, self.model, order_by)
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

    async def update(self, id: PkType, **data: Any) -> ModelT:
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

    async def delete(self, id: PkType) -> bool:
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
        stmt = _apply_filters(stmt, self.model, filters)
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
        stmt = _apply_filters(stmt, self.model, filters)
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
        stmt = _apply_filters(stmt, self.model, filters)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def bulk_create(self, items: List[dict[str, Any]]) -> List[ModelT]:
        """Insert multiple records in a single flush.

        Args:
            items: List of dicts, each containing column-value pairs.

        Returns:
            List of newly created model instances.
        """
        if not items:
            return []
        from sqlalchemy import insert
        stmt = insert(self.model).returning(self.model)
        result = await self.session.scalars(stmt, items)
        return list(result.all())

    async def bulk_update(
        self,
        ids: List[PkType],
        **data: Any,
    ) -> List[ModelT]:
        """Update the same set of fields on multiple records at once.

        Executes a single UPDATE … WHERE id IN (…) instead of N individual
        updates.

        Args:
            ids: Primary-key values of the records to update.
            **data: Column values to set on every matched record.

        Returns:
            List of updated model instances in unspecified order.

        Raises:
            NotFoundException: If any id in *ids* does not exist.
        """
        from sqlalchemy import update as _update

        unique_ids = list(dict.fromkeys(ids))  # deduplicate, preserve order

        count_result = await self.session.execute(
            select(func.count())
            .select_from(self.model)
            .where(self.model.id.in_(unique_ids))
        )
        if (count_result.scalar() or 0) != len(unique_ids):
            from aura.exceptions.http import NotFoundException
            raise NotFoundException(
                f"{self.model.__name__}: one or more ids not found"
            )

        await self.session.execute(
            _update(self.model)
            .where(self.model.id.in_(unique_ids))
            .values(**data)
            .execution_options(synchronize_session=False)
        )
        # Expire stale identity-map entries so the SELECT below reads fresh data.
        for obj in list(self.session.identity_map.values()):
            if isinstance(obj, self.model) and getattr(obj, "id", None) in unique_ids:
                self.session.expire(obj)

        result = await self.session.execute(
            select(self.model).where(self.model.id.in_(unique_ids))
        )
        return list(result.scalars().all())

    async def bulk_delete(self, ids: List[PkType]) -> int:
        """Delete multiple records by primary key in a single query.

        Executes a single DELETE … WHERE id IN (…) instead of N individual
        deletes.  Missing ids are silently skipped.

        Args:
            ids: Primary-key values of the records to delete.

        Returns:
            Number of records actually deleted.
        """
        from sqlalchemy import delete as _delete

        # AsyncSession.execute() is typed as Result[Any] for all statements, but
        # DML operations return CursorResult at runtime — cast reflects reality.
        result = cast(
            CursorResult[Any],
            await self.session.execute(
                _delete(self.model)
                .where(self.model.id.in_(ids))
                .execution_options(synchronize_session="fetch")
            ),
        )
        return result.rowcount

    async def paginate(
        self,
        *,
        page: int = 1,
        per_page: int = 20,
        order_by: str | None = None,
        **filters: Any,
    ) -> Page[ModelT]:
        """Fetch a paginated list of records.

        Args:
            page: Page number (starting from 1). Must be >= 1.
            per_page: Number of records per page.
            order_by: Column name to order by; prefix with ``-`` for DESC.
            **filters: Equality filters (column=value).

        Returns:
            A Page object containing items, total count, and pagination metadata.

        Raises:
            ValueError: If page < 1.
        """
        if page < 1:
            from aura.exceptions.http import UnprocessableEntityException
            raise UnprocessableEntityException("Page must be >= 1")

        # count query with filters applied
        count_stmt = select(func.count()).select_from(self.model)
        count_stmt = _apply_filters(count_stmt, self.model, filters)
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        # data query with filters, ordering, and pagination
        offset = (page - 1) * per_page
        stmt = select(self.model)
        stmt = _apply_filters(stmt, self.model, filters)
        if order_by:
            stmt = _apply_order_by(stmt, self.model, order_by)
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

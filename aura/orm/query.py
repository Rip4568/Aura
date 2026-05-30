"""AuraQL — fluent async query builder for AuraModel."""
from __future__ import annotations

import builtins
from typing import Any, Generic, TypeVar, cast

from sqlalchemy import and_, asc, desc, func, select, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from aura.orm.base import AuraModel

ModelT = TypeVar("ModelT", bound=AuraModel)


class MultipleObjectsReturnedException(Exception):  # noqa: N818  # Django-style naming — intentional, matches NotFoundException convention
    """Raised by QuerySet.get() when more than one object matches."""


class QuerySet(Generic[ModelT]):
    """Fluent async query builder for AuraModel subclasses.

    All filter/ordering/slicing methods return a new QuerySet (immutable chain).
    The query is only executed when a terminal method is called.

    Usage::

        async with db.session() as session:
            posts = await (
                Post.objects
                .using(session)
                .filter(active=True)
                .include("author", "tags")
                .order_by("-created_at")
                .limit(20)
                .all()
            )
    """

    def __init__(
        self,
        model: type[ModelT],
        session: AsyncSession | None = None,
    ) -> None:
        self._model = model
        self._session = session
        self._filters: builtins.list[Any] = []
        self._excludes: builtins.list[Any] = []
        self._order_by_clauses: builtins.list[Any] = []
        self._limit_val: int | None = None
        self._offset_val: int = 0
        self._prefetch_related: builtins.list[str] = []   # selectinload
        self._select_related: builtins.list[str] = []     # joinedload
        self._distinct_flag: bool = False
        self._for_update_flag: bool = False

    # ── Session binding ────────────────────────────────────────────────────

    def using(self, session: AsyncSession) -> QuerySet[ModelT]:
        """Bind a session to this QuerySet. Required before executing any terminal method."""
        qs = self._clone()
        qs._session = session
        return qs

    # ── Filtering ─────────────────────────────────────────────────────────

    def filter(self, *q_objects: Any, **kwargs: Any) -> QuerySet[ModelT]:
        """Add AND conditions. Supports Q objects and keyword lookups.

        Examples::

            .filter(active=True)
            .filter(name__icontains="alice")
            .filter(Q(active=True) | Q(role="admin"))
        """
        from aura.orm.lookups import resolve_lookup
        qs = self._clone()
        for q in q_objects:
            qs._filters.append(q._to_sqla(self._model))
        for key, value in kwargs.items():
            qs._filters.append(resolve_lookup(self._model, key, value))
        return qs

    def exclude(self, *q_objects: Any, **kwargs: Any) -> QuerySet[ModelT]:
        """Exclude objects matching the given conditions (NOT AND)."""
        from aura.orm.lookups import resolve_lookup
        qs = self._clone()
        conditions: builtins.list[Any] = [q._to_sqla(self._model) for q in q_objects]
        conditions += [resolve_lookup(self._model, k, v) for k, v in kwargs.items()]
        if conditions:
            qs._excludes.append(~and_(*conditions))
        return qs

    # ── Ordering ──────────────────────────────────────────────────────────

    def order_by(self, *fields: str) -> QuerySet[ModelT]:
        """Order results. Prefix '-' for descending.

        Example: .order_by("-created_at", "name")
        """
        qs = self._clone()
        for field in fields:
            if field.startswith("-"):
                col = getattr(self._model, field[1:])
                qs._order_by_clauses.append(desc(col))
            else:
                col = getattr(self._model, field)
                qs._order_by_clauses.append(asc(col))
        return qs

    # ── Slicing ───────────────────────────────────────────────────────────

    def limit(self, n: int) -> QuerySet[ModelT]:
        """Limit the number of results returned."""
        qs = self._clone()
        qs._limit_val = n
        return qs

    def offset(self, n: int) -> QuerySet[ModelT]:
        """Skip the first n results."""
        qs = self._clone()
        qs._offset_val = n
        return qs

    def page(self, number: int, size: int = 20) -> QuerySet[ModelT]:
        """Shortcut for .limit(size).offset((number-1)*size)."""
        return self.limit(size).offset((number - 1) * size)

    # ── Eager loading ─────────────────────────────────────────────────────

    def include(self, *relationships: str) -> QuerySet[ModelT]:
        """Eager-load relationships using selectinload (avoids N+1).

        Supports nested: .include("author.profile")
        Supports multiple: .include("author", "tags", "comments")

        selectinload issues one extra SELECT per relationship (safe for async,
        correct for one-to-many and many-to-many).
        """
        qs = self._clone()
        qs._prefetch_related = list(self._prefetch_related) + list(relationships)
        return qs

    def select_related(self, *relationships: str) -> QuerySet[ModelT]:
        """Eager-load to-one relationships using joinedload (single JOIN query).

        More efficient than include() for many-to-one and one-to-one.
        """
        qs = self._clone()
        qs._select_related = list(self._select_related) + list(relationships)
        return qs

    # ── Modifiers ─────────────────────────────────────────────────────────

    def distinct(self) -> QuerySet[ModelT]:
        """Add DISTINCT to the query."""
        qs = self._clone()
        qs._distinct_flag = True
        return qs

    def for_update(self) -> QuerySet[ModelT]:
        """Add SELECT FOR UPDATE locking."""
        qs = self._clone()
        qs._for_update_flag = True
        return qs

    # ── Terminal methods ───────────────────────────────────────────────────

    async def all(self) -> builtins.list[ModelT]:
        """Execute the query and return all results."""
        stmt = self._build_stmt()
        result = await self._get_session().execute(stmt)
        return list(result.scalars().unique().all())

    async def first(self) -> ModelT | None:
        """Return the first result or None."""
        stmt = self._build_stmt().limit(1)
        result = await self._get_session().execute(stmt)
        row = result.scalars().first()
        return cast(ModelT, row) if row is not None else None

    async def last(self) -> ModelT | None:
        """Return the last result (by primary key desc) or None."""
        qs = self._clone()
        qs._order_by_clauses = [desc(self._model.id)]
        qs._limit_val = 1
        stmt = qs._build_stmt()
        result = await self._get_session().execute(stmt)
        row = result.scalars().first()
        return cast(ModelT, row) if row is not None else None

    async def get(self, **kwargs: Any) -> ModelT:
        """Return exactly one object. Raises if 0 or more than 1 found."""
        from aura.exceptions.http import NotFoundException
        qs = self.filter(**kwargs) if kwargs else self
        stmt = qs._build_stmt()
        result = await self._get_session().execute(stmt)
        rows = list(result.scalars().unique().all())
        if not rows:
            raise NotFoundException(f"{self._model.__name__} not found.")
        if len(rows) > 1:
            raise MultipleObjectsReturnedException(
                f"get() returned {len(rows)} objects for {self._model.__name__}."
            )
        return cast(ModelT, rows[0])

    async def get_or_none(self, **kwargs: Any) -> ModelT | None:
        """Like get() but returns None instead of raising NotFoundException."""
        from aura.exceptions.http import NotFoundException
        try:
            return await self.get(**kwargs)
        except NotFoundException:
            return None

    async def count(self) -> int:
        """Return the count of matching records."""
        stmt = (
            select(func.count())
            .select_from(self._model)
        )
        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))
        result = await self._get_session().execute(stmt)
        return result.scalar() or 0

    async def exists(self) -> bool:
        """Return True if at least one matching record exists."""
        return await self.count() > 0

    async def paginate(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> Any:
        """Return a Page[ModelT] with items and metadata. Executes 2 queries."""
        from aura.orm.repository import Page
        total = await self.count()
        items = await self.page(page, per_page).all()
        return Page(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            has_next=page * per_page < total,
        )

    async def aggregate(self, **kwargs: Any) -> dict[str, Any]:
        """Compute aggregate values over matching records in a single query.

        Example::

            stats = await Post.objects.using(session).filter(active=True).aggregate(
                total=Count("id"),
                avg_views=Avg("view_count"),
                max_views=Max("view_count"),
            )
            # {"total": 42, "avg_views": 13.7, "max_views": 500}
        """
        from aura.orm.aggregates import Aggregate

        columns = []
        labels: builtins.list[str] = []
        for label, agg in kwargs.items():
            if not isinstance(agg, Aggregate):
                raise TypeError(
                    f"Expected an Aggregate instance for '{label}', "
                    f"got {type(agg).__name__}. Use Count(), Sum(), Avg(), Min() or Max()."
                )
            columns.append(agg._to_sqla(self._model).label(label))
            labels.append(label)

        stmt = select(*columns).select_from(self._model)
        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))

        result = await self._get_session().execute(stmt)
        row = result.one()
        return {label: getattr(row, label) for label in labels}

    async def values(self, *fields: str) -> builtins.list[dict[str, Any]]:
        """Return dicts instead of model instances.

        Example::

            rows = await User.objects.using(session).filter(active=True).values("id", "name")
            # [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]

        With no arguments, returns all columns as dicts (equivalent to .to_dict()).
        """
        if fields:
            columns: builtins.list[Any] = [getattr(self._model, f) for f in fields]
            stmt = select(*columns)
        else:
            stmt = select(self._model)

        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))
        if self._order_by_clauses:
            stmt = stmt.order_by(*self._order_by_clauses)
        if self._limit_val is not None:
            stmt = stmt.limit(self._limit_val)
        if self._offset_val:
            stmt = stmt.offset(self._offset_val)

        result = await self._get_session().execute(stmt)
        if fields:
            return [dict(zip(fields, row)) for row in result.all()]
        return [obj.to_dict() for obj in result.scalars().all()]

    async def values_list(
        self,
        *fields: str,
        flat: bool = False,
    ) -> builtins.list[Any]:
        """Return tuples, or flat values when flat=True and only one field given.

        Example::

            ids = await User.objects.using(session).values_list("id", flat=True)
            # [1, 2, 3]

            pairs = await User.objects.using(session).values_list("id", "name")
            # [(1, "Alice"), (2, "Bob")]
        """
        if not fields:
            raise ValueError("values_list() requires at least one field name.")
        if flat and len(fields) > 1:
            raise ValueError("values_list(flat=True) requires exactly one field.")

        columns_vl: builtins.list[Any] = [getattr(self._model, f) for f in fields]
        stmt = select(*columns_vl)
        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))
        if self._order_by_clauses:
            stmt = stmt.order_by(*self._order_by_clauses)
        if self._limit_val is not None:
            stmt = stmt.limit(self._limit_val)
        if self._offset_val:
            stmt = stmt.offset(self._offset_val)

        result = await self._get_session().execute(stmt)
        rows = result.all()
        if flat:
            return [row[0] for row in rows]
        return [tuple(row) for row in rows]

    async def delete(self) -> int:
        """Delete all matching records. Returns count deleted."""
        from sqlalchemy import delete as _delete
        stmt = _delete(self._model)
        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))
        stmt = stmt.execution_options(synchronize_session="fetch")
        result = cast(CursorResult[Any], await self._get_session().execute(stmt))
        return result.rowcount

    async def update(self, **data: Any) -> int:
        """Update all matching records. Returns count updated."""
        from sqlalchemy import update as _update
        stmt = _update(self._model)
        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))
        stmt = stmt.values(**data).execution_options(synchronize_session=False)
        result = cast(CursorResult[Any], await self._get_session().execute(stmt))
        return result.rowcount

    # ── Debug ─────────────────────────────────────────────────────────────

    def sql(self) -> str:
        """Return the compiled SQL string without executing.

        Uses SQLite dialect with literal binds for readability.
        """
        from sqlalchemy.dialects import sqlite
        stmt = self._build_stmt()
        return str(stmt.compile(
            dialect=sqlite.dialect(),
            compile_kwargs={"literal_binds": True},
        ))

    async def explain(self) -> str:
        """Run EXPLAIN on the query and return formatted output.

        Uses EXPLAIN QUERY PLAN for SQLite, EXPLAIN (ANALYZE) for PostgreSQL.
        """
        stmt = self._build_stmt()
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        sql_str = str(compiled)

        session = self._get_session()
        # Detect dialect from the engine URL via the bind
        bind = session.get_bind()
        dialect_name: str = bind.dialect.name if hasattr(bind, "dialect") else "sqlite"

        if dialect_name == "postgresql":
            explain_sql = f"EXPLAIN (ANALYZE, FORMAT TEXT) {sql_str}"
        else:
            explain_sql = f"EXPLAIN QUERY PLAN {sql_str}"

        result = await session.execute(text(explain_sql))
        rows = result.fetchall()
        return "\n".join(str(row) for row in rows)

    # ── Internals ─────────────────────────────────────────────────────────

    def _build_stmt(self) -> Any:
        """Compile the SQLAlchemy SELECT statement."""
        stmt = select(self._model)

        # Conditions
        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))

        # Eager loading — selectinload (one-to-many, many-to-many)
        for rel_path in self._prefetch_related:
            loader = _build_loader(self._model, rel_path, strategy="selectin")
            if loader is not None:
                stmt = stmt.options(loader)

        # Eager loading — joinedload (many-to-one, one-to-one)
        for rel_path in self._select_related:
            loader = _build_loader(self._model, rel_path, strategy="joined")
            if loader is not None:
                stmt = stmt.options(loader)

        # Ordering
        if self._order_by_clauses:
            stmt = stmt.order_by(*self._order_by_clauses)

        # Pagination
        if self._limit_val is not None:
            stmt = stmt.limit(self._limit_val)
        if self._offset_val:
            stmt = stmt.offset(self._offset_val)

        if self._distinct_flag:
            stmt = stmt.distinct()

        if self._for_update_flag:
            stmt = stmt.with_for_update()

        return stmt

    def _clone(self) -> QuerySet[ModelT]:
        """Create a shallow copy for immutability."""
        qs: QuerySet[ModelT] = QuerySet(self._model, self._session)
        qs._filters = list(self._filters)
        qs._excludes = list(self._excludes)
        qs._order_by_clauses = list(self._order_by_clauses)
        qs._limit_val = self._limit_val
        qs._offset_val = self._offset_val
        qs._prefetch_related = list(self._prefetch_related)
        qs._select_related = list(self._select_related)
        qs._distinct_flag = self._distinct_flag
        qs._for_update_flag = self._for_update_flag
        return qs

    def _get_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                f"QuerySet<{self._model.__name__}> has no session. "
                f"Call .using(session) before executing: "
                f"Post.objects.using(session).filter(...).all()"
            )
        return self._session

    def __repr__(self) -> str:
        return f"QuerySet<{self._model.__name__}>"


def _build_loader(model: type[Any], rel_path: str, strategy: str = "selectin") -> Any:
    """Build a selectinload or joinedload option for a relationship path.

    Supports nested: "author.profile" -> selectinload(Post.author).selectinload(User.profile)
    """
    from sqlalchemy import inspect as sa_inspect

    parts = rel_path.split(".")
    current_model = model
    loader: Any = None

    for part in parts:
        rel_attr = getattr(current_model, part, None)
        if rel_attr is None:
            raise AttributeError(
                f"Model '{current_model.__name__}' has no relationship '{part}'. "
                f"Check that '{part}' is defined as a SQLAlchemy relationship."
            )

        if loader is None:
            loader = selectinload(rel_attr) if strategy == "selectin" else joinedload(rel_attr)
        else:
            loader = loader.selectinload(rel_attr)

        # Advance to the next model in the chain
        try:
            mapper = sa_inspect(current_model)
            rel = mapper.relationships.get(part)
            if rel is not None:
                current_model = rel.mapper.class_
        except Exception:
            break

    return loader

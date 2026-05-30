"""Base ORM model for Aura — wraps SQLAlchemy DeclarativeBase with sensible defaults."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class _AuraRegistry(DeclarativeBase):
    """Internal SQLAlchemy registry. Never subclass this directly — use AuraModel."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)



class _QuerySetDescriptor:
    """Descriptor that returns a fresh QuerySet when accessed as a class attribute."""

    def __get__(self, obj: Any, objtype: type[Any] | None = None) -> Any:
        from aura.orm.query import QuerySet
        if objtype is None:
            objtype = type(obj)
        return QuerySet(objtype)


class QueryMixin:
    """Adds .objects class attribute to AuraModel for fluent queries."""

    objects: ClassVar[Any] = _QuerySetDescriptor()


class AuraModel(_AuraRegistry, QueryMixin):
    """Base class for all Aura ORM models.

    Provides automatic:

    * ``id`` — integer primary key (auto-increment)
    * ``created_at`` — timestamp set on insert
    * ``updated_at`` — timestamp updated on every write
    * :meth:`to_dict` — serialise all columns to a plain dict
    * ``__repr__`` — readable representation

    Usage::

        from aura.orm import AuraModel
        from sqlalchemy.orm import Mapped, mapped_column

        class User(AuraModel):
            __tablename__ = "users"

            name: Mapped[str]
            email: Mapped[str] = mapped_column(unique=True)

        # Works seamlessly with Aura schemas:
        user = await user_repo.get(1)
        schema = UserSchema.model_validate(user.to_dict())

    Intermediate abstract models are also supported::

        class TimestampedModel(AuraModel):
            __abstract__ = True
            deleted_at: Mapped[datetime | None] = mapped_column(nullable=True, default=None)

        class Post(TimestampedModel):
            __tablename__ = "posts"
            title: Mapped[str]
    """

    __abstract__ = True

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise all table columns to a plain Python dictionary."""
        from sqlalchemy import inspect as sa_inspect

        ins = sa_inspect(self)
        # Avoid triggering lazy-loading on deferred or unloaded columns to prevent errors.
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns
            if col.name not in ins.unloaded
        }

    def __repr__(self) -> str:
        pk = getattr(self, "id", "?")
        return f"<{self.__class__.__name__} id={pk}>"

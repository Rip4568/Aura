"""Base ORM model for Aura — wraps SQLAlchemy DeclarativeBase with sensible defaults."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AuraModel(DeclarativeBase):
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
    """

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
        """Serialise all table columns to a plain Python dictionary.

        Returns:
            A dict mapping column name to the current attribute value.
        """
        return {col.name: getattr(self, col.name) for col in self.__table__.columns}

    def __repr__(self) -> str:
        pk = getattr(self, "id", "?")
        return f"<{self.__class__.__name__} id={pk}>"

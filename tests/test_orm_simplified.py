"""Tests for Aura ORM simplified modeling (annotated types and semantic fields)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped

from aura.orm import (
    AuraModel,
    BooleanField,
    CharField,
    DatabaseManager,
    DecimalField,
    EmailField,
    ForeignKeyField,
    IntegerField,
    Repository,
    pk_int,
    relationship,
    str_255,
    text_long,
)

# ---------------------------------------------------------------------------
# Test Models
# ---------------------------------------------------------------------------

class SimplifiedUser(AuraModel):
    """Model using semantic fields wrappers (Alternativa B)."""

    __tablename__ = "simplified_users"

    name: Mapped[str] = CharField(max_length=150)
    email: Mapped[str | None] = EmailField(required=False, unique=True)
    is_active: Mapped[bool] = BooleanField(default=True)
    score: Mapped[int] = IntegerField(default=0)
    balance: Mapped[Decimal] = DecimalField(max_digits=12, decimal_places=4, default=Decimal("0.0"))


class SimplifiedPost(AuraModel):
    """Model using Annotated Types (Alternativa A) and ForeignKeyField."""

    __tablename__ = "simplified_posts"

    # Uses str_255 (which maps to String(255))
    title: Mapped[str_255]
    # Uses text_long (which maps to Text)
    content: Mapped[text_long]
    # Uses pk_int (which maps to Integer) and ForeignKeyField pointing to User class
    author_id: Mapped[pk_int] = ForeignKeyField(SimplifiedUser, required=True)

    # Standard relationship
    author: Mapped[SimplifiedUser] = relationship(SimplifiedUser, back_populates="posts")


# Add back_populates to SimplifiedUser to fully link them
SimplifiedUser.posts = relationship(SimplifiedPost, back_populates="author")


class UserRepository(Repository[SimplifiedUser]):
    model = SimplifiedUser


class PostRepository(Repository[SimplifiedPost]):
    model = SimplifiedPost


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db_manager() -> AsyncIterator[DatabaseManager]:
    """Provide a fresh in-memory SQLite DatabaseManager for simplified ORM tests."""
    manager = DatabaseManager()
    manager.init("sqlite+aiosqlite:///:memory:", echo=False)
    await manager.create_all(AuraModel)
    yield manager
    await manager.drop_all(AuraModel)
    await manager.close()


@pytest.fixture
async def session(db_manager: DatabaseManager) -> AsyncIterator[AsyncSession]:
    """Provide an AsyncSession within a rollback transaction."""
    async with db_manager.session() as s:
        yield s


@pytest.fixture
async def user_repo(session: AsyncSession) -> UserRepository:
    return UserRepository(session)


@pytest.fixture
async def post_repo(session: AsyncSession) -> PostRepository:
    return PostRepository(session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSimplifiedORM:
    """Integration tests for simplified fields and type annotations mapping."""

    async def test_create_and_query_simplified_user(self, user_repo: UserRepository) -> None:
        # Create a user using semantic fields
        user = await user_repo.create(
            name="Alice",
            email="alice@aura.dev",
            score=100,
            balance=Decimal("1500.50"),
        )
        assert user.id is not None
        assert user.name == "Alice"
        assert user.email == "alice@aura.dev"
        assert user.is_active is True
        assert user.score == 100
        assert user.balance == Decimal("1500.50")

        # Query it back
        fetched = await user_repo.get(user.id)
        assert fetched is not None
        assert fetched.name == "Alice"
        assert fetched.score == 100
        assert fetched.balance == Decimal("1500.50")

    async def test_create_and_query_simplified_post(
        self,
        user_repo: UserRepository,
        post_repo: PostRepository,
    ) -> None:
        # Create author first
        author = await user_repo.create(name="Author A", email="author@aura.dev")
        
        # Create a post using annotated types and ForeignKeyField
        post = await post_repo.create(
            title="My First Post",
            content="This is the content of the post.",
            author_id=author.id,
        )
        assert post.id is not None
        assert post.title == "My First Post"
        assert post.content == "This is the content of the post."
        assert post.author_id == author.id

        # Query back and verify relations
        fetched = await post_repo.first(title="My First Post")
        assert fetched is not None
        assert fetched.content == "This is the content of the post."
        
        # Access relationship
        assert fetched.author is not None
        assert fetched.author.name == "Author A"

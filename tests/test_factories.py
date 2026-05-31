"""Tests for Aura ORM Factories and Faker system."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from aura.orm import AuraModel, db
from aura.orm.factories import Factory, SubFactory
from aura.orm.session import current_session
from tests.test_orm_simplified import SimplifiedPost, SimplifiedUser


# 1. Definição das Factories
class UserFactory(Factory[SimplifiedUser]):
    model = SimplifiedUser

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.faker.name(),
            "email": lambda: self.faker.email(),
            "score": 10,
            "balance": Decimal("100.00"),
            "is_active": True,
        }


class PostFactory(Factory[SimplifiedPost]):
    model = SimplifiedPost

    def definition(self) -> dict[str, Any]:
        return {
            "title": self.faker.sentence(),
            "content": "Default post content",
            "author": SubFactory(UserFactory),
        }


# Class Base sem definição para testar NotImplementedError
class BaseWithoutDefinitionFactory(Factory[SimplifiedUser]):
    model = SimplifiedUser


# Class sem ModelT ou model para testar erro de modelo não configurado
class ModelMissingFactory(Factory[Any]):
    def definition(self) -> dict[str, Any]:
        return {}


# 2. Configuração do Banco de Dados usando o db global
@pytest.fixture(autouse=True)
async def setup_db() -> Any:
    """Setup and clean the global database connection for tests."""
    db.init("sqlite+aiosqlite:///:memory:", echo=False)
    await db.create_all(AuraModel)
    yield
    await db.close()


class TestFactories:
    """Comprehensive test suite for Factories, SubFactories and Faker integration."""

    # --- Testes de make() ---
    def test_make_in_memory(self) -> None:
        """Test generating a model in memory with make()."""
        factory = UserFactory()
        user = factory.make()

        assert isinstance(user, SimplifiedUser)
        assert user.id is None  # Não persistido
        assert isinstance(user.name, str)
        assert len(user.name) > 0
        assert "@" in user.email
        assert user.score == 10
        assert user.balance == Decimal("100.00")
        assert user.is_active is True

    def test_make_overrides(self) -> None:
        """Test overriding attributes on make()."""
        user = UserFactory().make(name="Jhone Doe", score=99, is_active=False)

        assert user.name == "Jhone Doe"
        assert user.score == 99
        assert user.is_active is False

    def test_make_state_immutable(self) -> None:
        """Test Factory.state() returns a new instance and accumulates overrides."""
        factory = UserFactory()
        admin_factory = factory.state(score=500, is_active=True)

        assert factory is not admin_factory
        assert factory._overrides == {}
        assert admin_factory._overrides == {"score": 500, "is_active": True}

        user1 = factory.make()
        user2 = admin_factory.make()

        assert user1.score == 10
        assert user2.score == 500

    def test_make_many(self) -> None:
        """Test batch generation in memory."""
        users = UserFactory().make_many(5, score=25)

        assert len(users) == 5
        for user in users:
            assert isinstance(user, SimplifiedUser)
            assert user.score == 25
            assert user.id is None

    def test_make_sub_factory(self) -> None:
        """Test recursive SubFactory resolution with make()."""
        post = PostFactory().make(title="Custom Title")

        assert isinstance(post, SimplifiedPost)
        assert post.title == "Custom Title"
        assert post.content == "Default post content"
        assert isinstance(post.author, SimplifiedUser)
        assert post.author.id is None  # Sub-objeto também não está persistido
        assert post.author.score == 10

    # --- Testes de create() ---
    async def test_create_isolated_session(self) -> None:
        """Test create() with an isolated session (no current_session context)."""
        assert current_session.get() is None

        user = await UserFactory().create(name="Isolated User")

        assert user.id is not None
        # Consultar no banco para verificar persistência real
        async with db.session() as s:
            db_user = await s.get(SimplifiedUser, user.id)
            assert db_user is not None
            assert db_user.name == "Isolated User"

    async def test_create_with_active_session(self) -> None:
        """Test create() reusing the active current_session ContextVar."""
        async with db.session() as s:
            token = current_session.set(s)
            try:
                user = await UserFactory().create(name="Session User")
                assert user.id is not None

                # Como a sessão está ativa e não fez commit ainda (apenas flush),
                # o usuário deve estar na sessão atual.
                db_user = await s.get(SimplifiedUser, user.id)
                assert db_user is not None
                assert db_user.name == "Session User"
            finally:
                current_session.reset(token)

    async def test_create_sub_factory(self) -> None:
        """Test that SubFactory resolves recursively and persists related objects with create()."""
        post = await PostFactory().create(title="Aura Core")

        assert post.id is not None
        assert post.author_id is not None

        # Verificar se ambos foram realmente salvos no banco e o relacionamento é válido
        async with db.session() as s:
            db_post = await s.get(SimplifiedPost, post.id)
            db_user = await s.get(SimplifiedUser, post.author_id)
            assert db_post is not None
            assert db_post.title == "Aura Core"
            assert db_user is not None
            assert db_user.id == post.author_id
            
            # Acessar relacionamento de forma segura dentro de uma sessão ativa
            assert db_post.author is not None
            assert db_post.author.id == db_user.id

    async def test_create_many_isolated_session(self) -> None:
        """Test create_many() creating a batch in a single isolated session."""
        users = await UserFactory().create_many(3, score=42)

        assert len(users) == 3
        for user in users:
            assert user.id is not None
            assert user.score == 42

        # Verificar no banco
        async with db.session() as s:
            for user in users:
                db_user = await s.get(SimplifiedUser, user.id)
                assert db_user is not None
                assert db_user.score == 42

    async def test_create_many_active_session(self) -> None:
        """Test create_many() reusing an active session."""
        async with db.session() as s:
            token = current_session.set(s)
            try:
                users = await UserFactory().create_many(3, score=84)
                assert len(users) == 3
                for user in users:
                    assert user.id is not None
            finally:
                current_session.reset(token)

    # --- Testes de Erros e Exceções ---
    def test_not_implemented_definition(self) -> None:
        """Test raising NotImplementedError when definition() is not implemented."""
        with pytest.raises(NotImplementedError, match="Factories must implement the definition"):
            BaseWithoutDefinitionFactory().make()

    def test_missing_model_configuration(self) -> None:
        """Test raising AttributeError when model is missing and cannot be inferred."""
        with pytest.raises(AttributeError, match="must define a 'model' attribute"):
            ModelMissingFactory().make()

    # --- Teste de Faker global ---
    def test_faker_integration(self) -> None:
        """Test that the global faker instance is working correctly."""
        assert isinstance(UserFactory.faker, type(UserFactory().faker))
        # Deve ser capaz de chamar os métodos do Faker
        assert isinstance(UserFactory.faker.name(), str)
        assert isinstance(UserFactory.faker.email(), str)

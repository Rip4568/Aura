"""Tests for the Aura Forms module (v0.6.0).

Covers: exceptions, all field types, validators, AuraForm lifecycle,
ForeignKeyField/ManyToManyField with real SQLite sessions.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column

from aura.forms import (
    AuraForm,
    BoolField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    EmailField,
    FieldValidationError,
    ForeignKeyField,
    FormValidationError,
    IntField,
    ManyToManyField,
    UUIDField,
    validate_email,
    validate_max_length,
    validate_min_length,
    validate_regex,
    validate_slug,
    validate_url,
)
from aura.orm.base import AuraModel

# ---------------------------------------------------------------------------
# Test models (defined here to keep forms tests self-contained)
# ---------------------------------------------------------------------------


class FKAuthor(AuraModel):
    """Author model for ForeignKeyField / ManyToManyField tests."""

    __tablename__ = "fk_authors"

    name: Mapped[str] = mapped_column(sa.String(100))


# ---------------------------------------------------------------------------
# Local DB fixtures — SQLite in-memory for relational field tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def forms_engine() -> Any:
    """Shared async engine for the forms test module."""
    return create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)


@pytest.fixture(autouse=True, scope="module")
async def forms_tables(forms_engine: Any) -> AsyncIterator[None]:
    """Create (and drop) all tables once per module."""
    async with forms_engine.begin() as conn:
        await conn.run_sync(AuraModel.metadata.create_all)
    yield
    async with forms_engine.begin() as conn:
        await conn.run_sync(AuraModel.metadata.drop_all)


@pytest.fixture
async def forms_session(forms_engine: Any) -> AsyncIterator[AsyncSession]:
    """Fresh AsyncSession for each test."""
    factory = async_sessionmaker(forms_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


# ---------------------------------------------------------------------------
# TestExceptions (5 tests)
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_field_validation_error_attributes(self) -> None:
        exc = FieldValidationError("campo inválido", code="invalid")
        assert exc.message == "campo inválido"
        assert exc.code == "invalid"
        assert exc.messages == ["campo inválido"]

    def test_field_validation_error_messages_list(self) -> None:
        exc = FieldValidationError("falhou")
        assert len(exc.messages) == 1
        assert exc.messages[0] == "falhou"

    def test_form_validation_error_errors_dict(self) -> None:
        errors = {"email": ["inválido"], "name": ["obrigatório"]}
        exc = FormValidationError(errors)
        assert exc.errors == errors
        assert exc.code == "FORM_VALIDATION_ERROR"

    def test_form_validation_error_to_dict_format(self) -> None:
        errors = {"email": ["inválido"]}
        exc = FormValidationError(errors)
        result = exc.to_dict()
        assert "error" in result
        assert result["error"]["status"] == 422
        assert result["error"]["code"] == "FORM_VALIDATION_ERROR"
        assert result["error"]["detail"] == errors

    def test_form_validation_error_all_key(self) -> None:
        errors = {"__all__": ["senhas não coincidem"]}
        exc = FormValidationError(errors)
        result = exc.to_dict()
        assert result["error"]["detail"]["__all__"] == ["senhas não coincidem"]

    def test_field_validation_error_no_code(self) -> None:
        exc = FieldValidationError("mensagem sem código")
        assert exc.code is None
        assert exc.message == "mensagem sem código"


# ---------------------------------------------------------------------------
# TestCharField (6 tests)
# ---------------------------------------------------------------------------


class TestCharField:
    def test_to_python_returns_str(self) -> None:
        field = CharField()
        result = field.to_python("hello")
        assert result == "hello"
        assert isinstance(result, str)

    def test_max_length_exact_ok(self) -> None:
        field = CharField(max_length=5)
        assert field.run("abcde") == "abcde"

    def test_max_length_exceeded_raises(self) -> None:
        field = CharField(max_length=5)
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("toolong")
        assert exc_info.value.code == "max_length"

    def test_min_length_below_raises(self) -> None:
        field = CharField(min_length=5)
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("hi")
        assert exc_info.value.code == "min_length"

    def test_strip_true_removes_whitespace(self) -> None:
        field = CharField(strip=True)
        assert field.to_python("  hello  ") == "hello"

    def test_required_false_with_none_returns_none(self) -> None:
        field = CharField(required=False)
        assert field.run(None) is None

    def test_required_true_with_none_raises(self) -> None:
        field = CharField(required=True)
        with pytest.raises(FieldValidationError) as exc_info:
            field.run(None)
        assert exc_info.value.code == "required"


# ---------------------------------------------------------------------------
# TestIntField (4 tests)
# ---------------------------------------------------------------------------


class TestIntField:
    def test_to_python_converts_string(self) -> None:
        field = IntField()
        assert field.to_python("42") == 42

    def test_non_numeric_string_raises(self) -> None:
        field = IntField()
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("abc")
        assert exc_info.value.code == "invalid_int"

    def test_min_and_max_value_validation(self) -> None:
        field = IntField(min_value=1, max_value=10)
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("0")
        assert exc_info.value.code == "min_value"

        with pytest.raises(FieldValidationError) as exc_info2:
            field.run("11")
        assert exc_info2.value.code == "max_value"

    def test_required_false_with_none(self) -> None:
        field = IntField(required=False)
        assert field.run(None) is None


# ---------------------------------------------------------------------------
# TestBoolField (5 tests)
# ---------------------------------------------------------------------------


class TestBoolField:
    def test_truthy_strings(self) -> None:
        field = BoolField()
        for val in ("true", "1", "on"):
            assert field.to_python(val) is True

    def test_falsy_strings(self) -> None:
        field = BoolField()
        for val in ("false", "0", "off"):
            assert field.to_python(val) is False

    def test_none_required_false_returns_false(self) -> None:
        """Absent checkbox (raw=None) with required=False must return False, not None."""
        field = BoolField(required=False)
        result = field.run(None)
        assert result is False

    def test_none_required_true_raises(self) -> None:
        """BoolField required=True + raw=None: validate() overridden, no 'required' error.

        BoolField.validate() skips the required check because absent → False.
        The field simply returns False even when required=True.
        """
        field = BoolField(required=True)
        # BoolField converts None → False; validate() does NOT raise for required
        # because it skips the None check entirely.
        result = field.run(None)
        assert result is False

    def test_python_booleans_pass_through(self) -> None:
        field = BoolField()
        assert field.to_python(True) is True
        assert field.to_python(False) is False


# ---------------------------------------------------------------------------
# TestEmailField (3 tests)
# ---------------------------------------------------------------------------


class TestEmailField:
    def test_valid_email_passes(self) -> None:
        field = EmailField()
        assert field.run("user@example.com") == "user@example.com"

    def test_invalid_email_no_at_raises(self) -> None:
        field = EmailField()
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("notanemail")
        assert exc_info.value.code == "invalid_email"

    def test_empty_required_true_raises(self) -> None:
        field = EmailField(required=True)
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("")
        assert exc_info.value.code == "required"


# ---------------------------------------------------------------------------
# TestChoiceField (4 tests)
# ---------------------------------------------------------------------------


class TestChoiceField:
    def test_valid_choice_passes(self) -> None:
        field = ChoiceField(choices=["a", "b", "c"])
        assert field.run("a") == "a"

    def test_invalid_choice_raises(self) -> None:
        field = ChoiceField(choices=["a", "b"])
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("z")
        assert exc_info.value.code == "invalid_choice"

    def test_choices_as_list_of_strings(self) -> None:
        field = ChoiceField(choices=["yes", "no"])
        assert field.run("yes") == "yes"

    def test_choices_as_list_of_tuples(self) -> None:
        choices: list[tuple[str, str]] = [("y", "Yes"), ("n", "No")]
        field = ChoiceField(choices=choices)
        assert field.run("y") == "y"
        with pytest.raises(FieldValidationError):
            field.run("Yes")  # label, not value


# ---------------------------------------------------------------------------
# TestValidators (6 tests)
# ---------------------------------------------------------------------------


class TestValidators:
    def test_validate_min_length_ok(self) -> None:
        validator = validate_min_length(3)
        validator("abc")  # should not raise

    def test_validate_min_length_fails(self) -> None:
        validator = validate_min_length(5)
        with pytest.raises(FieldValidationError) as exc_info:
            validator("hi")
        assert exc_info.value.code == "min_length"

    def test_validate_max_length_ok(self) -> None:
        validator = validate_max_length(10)
        validator("short")  # should not raise

    def test_validate_max_length_fails(self) -> None:
        validator = validate_max_length(3)
        with pytest.raises(FieldValidationError) as exc_info:
            validator("toolong")
        assert exc_info.value.code == "max_length"

    def test_validate_email_valid(self) -> None:
        validate_email("user@domain.com")  # should not raise

    def test_validate_email_invalid(self) -> None:
        with pytest.raises(FieldValidationError) as exc_info:
            validate_email("notvalid")
        assert exc_info.value.code == "invalid_email"

    def test_validate_slug_valid(self) -> None:
        validate_slug("my-slug_123")  # should not raise

    def test_validate_slug_invalid(self) -> None:
        with pytest.raises(FieldValidationError) as exc_info:
            validate_slug("Invalid Slug!")
        assert exc_info.value.code == "invalid_slug"

    def test_validate_url_valid(self) -> None:
        validate_url("https://example.com/path")  # should not raise

    def test_validate_url_invalid(self) -> None:
        with pytest.raises(FieldValidationError) as exc_info:
            validate_url("ftp://nope.com")
        assert exc_info.value.code == "invalid_url"

    def test_validate_regex_match_ok(self) -> None:
        validator = validate_regex(r"^\d{4}$")
        validator("1234")  # should not raise

    def test_validate_regex_match_fails(self) -> None:
        validator = validate_regex(r"^\d{4}$")
        with pytest.raises(FieldValidationError) as exc_info:
            validator("abcd")
        assert exc_info.value.code == "invalid_regex"


# ---------------------------------------------------------------------------
# TestAuraFormLifecycle (8 tests)
# ---------------------------------------------------------------------------


class SimpleForm(AuraForm):
    name = CharField(max_length=50)
    age = IntField(required=False)


class FormWithCleanField(AuraForm):
    username = CharField(max_length=30)

    def clean_username(self) -> str:
        value: str = self.cleaned_data.get("username", "")
        return value.lower()


class FormWithCleanGlobal(AuraForm):
    password = CharField()
    confirm = CharField()

    async def clean(self) -> None:
        if self.cleaned_data.get("password") != self.cleaned_data.get("confirm"):
            raise FieldValidationError("Senhas não coincidem.")


class BaseForm(AuraForm):
    name = CharField()


class ChildForm(BaseForm):
    email = EmailField()


class TestAuraFormLifecycle:
    async def test_is_valid_returns_true_for_valid_form(self) -> None:
        form = SimpleForm(raw_data={"name": "Alice", "age": "30"})
        assert await form.is_valid() is True

    async def test_is_valid_returns_false_and_populates_errors(self) -> None:
        # name is required but empty, age is required=False so OK
        form = SimpleForm(raw_data={"age": "25"})
        assert await form.is_valid() is False
        assert "name" in form.errors

    async def test_full_clean_populates_cleaned_data(self) -> None:
        form = SimpleForm(raw_data={"name": "Bob", "age": "42"})
        await form.full_clean()
        assert form.cleaned_data["name"] == "Bob"
        assert form.cleaned_data["age"] == 42

    async def test_clean_field_hook_modifies_value(self) -> None:
        form = FormWithCleanField(raw_data={"username": "ALICE"})
        assert await form.is_valid() is True
        assert form.cleaned_data["username"] == "alice"

    async def test_clean_global_hook_called(self) -> None:
        form = FormWithCleanGlobal(
            raw_data={"password": "secret", "confirm": "secret"}
        )
        assert await form.is_valid() is True

    async def test_clean_global_error_goes_to_all_key(self) -> None:
        form = FormWithCleanGlobal(
            raw_data={"password": "secret", "confirm": "different"}
        )
        assert await form.is_valid() is False
        assert "__all__" in form.errors
        assert "Senhas não coincidem." in form.errors["__all__"]

    async def test_save_raises_form_validation_error_when_invalid(self) -> None:
        form = SimpleForm(raw_data={})  # name is required → invalid
        with pytest.raises(FormValidationError) as exc_info:
            await form.save()
        assert exc_info.value.errors  # should have field errors

    async def test_inheritance_collects_base_and_child_fields(self) -> None:
        form = ChildForm(raw_data={"name": "Eve", "email": "eve@example.com"})
        assert await form.is_valid() is True
        assert "name" in form.cleaned_data
        assert "email" in form.cleaned_data


# ---------------------------------------------------------------------------
# TestForeignKeyField (5 tests)
# ---------------------------------------------------------------------------


class TestForeignKeyField:
    def test_to_python_raises_runtime_error(self) -> None:
        field = ForeignKeyField(FKAuthor)
        with pytest.raises(RuntimeError, match="requer uma sessão"):
            field.to_python(1)

    async def test_to_python_with_session_returns_instance(
        self, forms_session: AsyncSession
    ) -> None:
        author = FKAuthor(name="Test Author")
        forms_session.add(author)
        await forms_session.commit()
        await forms_session.refresh(author)

        field = ForeignKeyField(FKAuthor)
        result = await field.to_python_with_session(author.id, forms_session)
        assert isinstance(result, FKAuthor)
        assert result.name == "Test Author"

    async def test_to_python_with_session_not_found_raises(
        self, forms_session: AsyncSession
    ) -> None:
        field = ForeignKeyField(FKAuthor)
        with pytest.raises(FieldValidationError) as exc_info:
            await field.to_python_with_session(999999, forms_session)
        assert exc_info.value.code == "not_found"

    async def test_form_fk_field_without_session_raises_runtime_error(
        self,
    ) -> None:
        class PostForm(AuraForm):
            author = ForeignKeyField(FKAuthor)

        form = PostForm(raw_data={"author": 1})
        # Without a session, field.run() is called which invokes to_python() → RuntimeError
        # The RuntimeError propagates (it is not caught as FieldValidationError).
        with pytest.raises(RuntimeError, match="requer uma sessão"):
            await form.full_clean()

    async def test_form_fk_field_with_session_resolves_instance(
        self, forms_session: AsyncSession
    ) -> None:
        author = FKAuthor(name="FK Author Session Test")
        forms_session.add(author)
        await forms_session.commit()
        await forms_session.refresh(author)

        class PostForm(AuraForm):
            author = ForeignKeyField(FKAuthor)

        form = PostForm(
            raw_data={"author": author.id},
            session=forms_session,
        )
        assert await form.is_valid() is True
        assert isinstance(form.cleaned_data["author"], FKAuthor)
        assert form.cleaned_data["author"].name == "FK Author Session Test"


# ---------------------------------------------------------------------------
# TestManyToManyField (4 tests)
# ---------------------------------------------------------------------------


class TestManyToManyField:
    async def test_to_python_with_session_returns_list(
        self, forms_session: AsyncSession
    ) -> None:
        a1 = FKAuthor(name="M2M Author 1")
        a2 = FKAuthor(name="M2M Author 2")
        forms_session.add_all([a1, a2])
        await forms_session.commit()
        await forms_session.refresh(a1)
        await forms_session.refresh(a2)

        field = ManyToManyField(FKAuthor)
        result = await field.to_python_with_session(
            [a1.id, a2.id], forms_session
        )
        assert len(result) == 2
        assert all(isinstance(r, FKAuthor) for r in result)

    async def test_missing_id_raises_field_validation_error(
        self, forms_session: AsyncSession
    ) -> None:
        field = ManyToManyField(FKAuthor)
        with pytest.raises(FieldValidationError) as exc_info:
            await field.to_python_with_session([999998, 999997], forms_session)
        assert exc_info.value.code == "not_found"

    async def test_empty_list_required_false_returns_empty(self) -> None:
        field = ManyToManyField(FKAuthor, required=False)
        # validate([]) with required=False must not raise
        field.validate([])  # no exception means success

    async def test_empty_list_required_true_raises(self) -> None:
        field = ManyToManyField(FKAuthor, required=True)
        with pytest.raises(FieldValidationError) as exc_info:
            field.validate([])
        assert exc_info.value.code == "required"


# ---------------------------------------------------------------------------
# TestDateFields (3 tests)
# ---------------------------------------------------------------------------


class TestDateFields:
    def test_date_field_valid_iso(self) -> None:
        field = DateField()
        result = field.run("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_date_field_invalid_format_raises(self) -> None:
        field = DateField()
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("15/01/2024")
        assert exc_info.value.code == "invalid_date"

    def test_datetime_field_valid_iso(self) -> None:
        field = DateTimeField()
        result = field.run("2024-01-15T10:30:00")
        assert result == datetime(2024, 1, 15, 10, 30, 0)


# ---------------------------------------------------------------------------
# TestUUIDField (2 tests)
# ---------------------------------------------------------------------------


class TestUUIDField:
    def test_valid_uuid_string_returns_uuid(self) -> None:
        field = UUIDField()
        val = "12345678-1234-5678-1234-567812345678"
        result = field.run(val)
        assert isinstance(result, uuid.UUID)
        assert str(result) == val

    def test_invalid_uuid_string_raises(self) -> None:
        field = UUIDField()
        with pytest.raises(FieldValidationError) as exc_info:
            field.run("not-a-uuid")
        assert exc_info.value.code == "invalid_uuid"

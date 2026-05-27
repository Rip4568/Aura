"""Tests for aura.schema module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aura.schema.base import ResponseSchema, Schema
from aura.schema.openapi import OpenAPIGenerator


class UserSchema(Schema):
    name: str
    email: str
    age: int = 0


class UserResponse(ResponseSchema):
    id: int
    name: str


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_schema_basic_validation() -> None:
    user = UserSchema(name="Alice", email="alice@example.com")
    assert user.name == "Alice"
    assert user.email == "alice@example.com"
    assert user.age == 0


def test_schema_strips_whitespace() -> None:
    user = UserSchema(name="  Alice  ", email="  alice@example.com  ")
    assert user.name == "Alice"
    assert user.email == "alice@example.com"


def test_schema_from_attributes() -> None:
    class FakeORM:
        name = "Bob"
        email = "bob@example.com"
        age = 25

    user = UserSchema.model_validate(FakeORM(), from_attributes=True)
    assert user.name == "Bob"
    assert user.age == 25


def test_schema_invalid_raises() -> None:
    with pytest.raises(ValidationError):
        UserSchema(name="Alice")  # missing email


def test_response_schema_inherits_schema() -> None:
    resp = UserResponse(id=1, name="Alice")
    assert resp.id == 1
    assert isinstance(resp, Schema)


# ---------------------------------------------------------------------------
# OpenAPI Generator tests
# ---------------------------------------------------------------------------


def test_openapi_generator_basic() -> None:
    gen = OpenAPIGenerator(title="Test API", version="1.0.0")
    spec = gen.generate()

    assert spec["openapi"] == "3.1.0"
    assert spec["info"]["title"] == "Test API"
    assert spec["info"]["version"] == "1.0.0"
    assert "paths" in spec
    assert "components" in spec


def test_openapi_generator_adds_route() -> None:
    gen = OpenAPIGenerator(title="Test API", version="1.0.0")
    gen.add_route(
        {
            "method": "GET",
            "path": "/users",
            "response": UserResponse,
            "status": 200,
            "tags": ["users"],
            "summary": "List users",
            "deprecated": False,
            "operation_id": "list_users",
        }
    )
    spec = gen.generate()

    assert "/users" in spec["paths"]
    assert "get" in spec["paths"]["/users"]
    assert spec["paths"]["/users"]["get"]["summary"] == "List users"
    assert "UserResponse" in spec["components"]["schemas"]


def test_openapi_generator_caches_spec() -> None:
    gen = OpenAPIGenerator(title="Test API", version="1.0.0")
    spec1 = gen.generate()
    spec2 = gen.generate()
    assert spec1 is spec2  # same object — cached


def test_openapi_generator_invalidate() -> None:
    gen = OpenAPIGenerator(title="Test API", version="1.0.0")
    spec1 = gen.generate()
    gen.invalidate()
    spec2 = gen.generate()
    assert spec1 is not spec2

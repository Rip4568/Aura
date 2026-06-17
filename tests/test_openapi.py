"""Tests for OpenAPI schema generation."""

from __future__ import annotations

from aura import Schema
from aura.schema.openapi import OpenAPIGenerator


class Address(Schema):
    """A nested model used for testing."""

    city: str
    zip_code: str


class User(Schema):
    """A model with a nested Address field."""

    name: str
    email: str
    address: Address


class TestOpenAPIGenerator:
    """Tests for the OpenAPIGenerator class."""

    def test_nested_models_flatten_defs(self) -> None:
        """Test that nested Pydantic models have $defs flattened into components.

        This test verifies that:
        1. $defs are not present in any schema in components/schemas
        2. refs use #/components/schemas/... format (not #/$defs/...)
        """
        generator = OpenAPIGenerator(
            title="Test API",
            version="1.0.0",
        )

        # Add routes with nested models
        generator.add_route(
            {
                "method": "POST",
                "path": "/users",
                "body": User,
                "response": User,
                "status": 201,
                "tags": [],
                "summary": "Create user",
                "operation_id": "create_user",
                "deprecated": False,
                "parameters": [],
            }
        )

        spec = generator.generate()
        components = spec["components"]["schemas"]

        # Verify that $defs is not present in any schema
        for schema_name, schema in components.items():
            assert (
                "$defs" not in schema
            ), f"Schema {schema_name} should not contain $defs: {schema}"

        # Verify that User and Address are both in components
        assert "User" in components, "User schema should be in components"
        assert (
            "Address" in components
        ), "Address schema should be in components (flattened from $defs)"

        # Verify that refs use correct format
        user_schema = components["User"]
        assert isinstance(
            user_schema, dict
        ), "User schema should be a dict (not just a reference)"

        address_ref = user_schema.get("properties", {}).get("address", {}).get("$ref")
        assert (
            address_ref == "#/components/schemas/Address"
        ), f"Address ref should use #/components/schemas format, got: {address_ref}"

    def test_single_model_no_refs(self) -> None:
        """Test that a simple model without nested types works correctly."""

        class SimpleModel(Schema):
            """A simple model without nesting."""

            id: int
            name: str

        generator = OpenAPIGenerator(
            title="Test API",
            version="1.0.0",
        )

        generator.add_route(
            {
                "method": "GET",
                "path": "/simple",
                "response": SimpleModel,
                "status": 200,
                "tags": [],
                "summary": "Get simple",
                "operation_id": "get_simple",
                "deprecated": False,
                "parameters": [],
            }
        )

        spec = generator.generate()
        components = spec["components"]["schemas"]

        # Should have only SimpleModel and validation error schemas
        assert "SimpleModel" in components
        assert "$defs" not in components["SimpleModel"]

    def test_multiple_nested_levels(self) -> None:
        """Test that deeply nested models are all flattened into components."""

        class Country(Schema):
            """Deepest level."""

            name: str
            code: str

        class Address2(Schema):
            """Middle level."""

            street: str
            country: Country

        class Person(Schema):
            """Top level with deeply nested model."""

            name: str
            address: Address2

        generator = OpenAPIGenerator(
            title="Test API",
            version="1.0.0",
        )

        generator.add_route(
            {
                "method": "POST",
                "path": "/people",
                "body": Person,
                "response": Person,
                "status": 201,
                "tags": [],
                "summary": "Create person",
                "operation_id": "create_person",
                "deprecated": False,
                "parameters": [],
            }
        )

        spec = generator.generate()
        components = spec["components"]["schemas"]

        # Verify no $defs in any schema
        for schema_name, schema in components.items():
            assert "$defs" not in schema, f"Schema {schema_name} has $defs"

        # All three models should be in components
        assert "Person" in components
        assert "Address2" in components
        assert "Country" in components

    def test_route_with_path_and_query_parameters(self) -> None:
        """Test that parameters (path and query) are included in the spec."""

        class UserResponse(Schema):
            """User response model."""

            id: int
            name: str

        generator = OpenAPIGenerator(
            title="Test API",
            version="1.0.0",
        )

        parameters = [
            {
                "name": "id",
                "in": "path",
                "required": True,
                "schema": {"type": "integer"},
            },
            {
                "name": "page",
                "in": "query",
                "required": False,
                "schema": {"type": "integer", "default": 1},
            },
        ]

        generator.add_route(
            {
                "method": "GET",
                "path": "/users/{id}",
                "response": UserResponse,
                "status": 200,
                "tags": ["users"],
                "summary": "Get user by ID",
                "operation_id": "get_user",
                "deprecated": False,
                "parameters": parameters,
            }
        )

        spec = generator.generate()
        paths = spec["paths"]

        # Check that the path exists with correct method
        assert "/users/{id}" in paths
        assert "get" in paths["/users/{id}"]

        # Check that parameters are present
        get_op = paths["/users/{id}"]["get"]
        assert "parameters" in get_op
        assert len(get_op["parameters"]) == 2

        # Verify path parameter
        path_param = next((p for p in get_op["parameters"] if p["name"] == "id"), None)
        assert path_param is not None
        assert path_param["in"] == "path"
        assert path_param["required"] is True

        # Verify query parameter
        query_param = next(
            (p for p in get_op["parameters"] if p["name"] == "page"), None
        )
        assert query_param is not None
        assert query_param["in"] == "query"

    def test_jwt_guard_security_schemes(self) -> None:
        """Routes protected by JWTGuard should expose BearerAuth in OpenAPI."""
        from aura.guards.jwt import JWTGuard

        guard = JWTGuard(secret="test-secret")
        generator = OpenAPIGenerator(title="Test API", version="1.0.0")
        generator.add_route(
            {
                "method": "GET",
                "path": "/me",
                "status": 200,
                "tags": ["auth"],
                "summary": "Current user",
                "operation_id": "get_me",
                "deprecated": False,
                "parameters": [],
                "guards": [guard],
            }
        )

        spec = generator.generate()
        security_schemes = spec["components"]["securitySchemes"]

        assert "BearerAuth" in security_schemes
        assert security_schemes["BearerAuth"] == {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
        assert spec["paths"]["/me"]["get"]["security"] == [{"BearerAuth": []}]

    def test_router_tags_merge(self) -> None:
        """Router-level tags should merge with route-level tags without duplicates."""
        from aura import get
        from aura.routing.router import Router

        @get("/items", tags=["items"])
        async def list_items() -> dict[str, str]:
            return {"ok": "true"}

        generator = OpenAPIGenerator(title="Test API", version="1.0.0")
        router = Router(prefix="/api", tags=["catalog"])
        router.add_handler(list_items)
        router.build_routes(openapi_gen=generator)

        spec = generator.generate()
        operation = spec["paths"]["/api/items"]["get"]
        assert operation["tags"] == ["catalog", "items"]

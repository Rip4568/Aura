"""OpenAPI 3.1 specification generator for the Aura framework."""

from __future__ import annotations

import inspect
from typing import Any

from pydantic import BaseModel


class OpenAPIGenerator:
    """
    Generates an OpenAPI 3.1 specification from collected route metadata.

    The generator is constructed once per :class:`~aura.core.app.Aura`
    instance and its output is cached after the first call to
    :meth:`generate`.
    """

    def __init__(
        self,
        title: str,
        version: str,
        description: str = "",
        servers: list[dict[str, str]] | None = None,
    ) -> None:
        self.title = title
        self.version = version
        self.description = description
        self.servers = servers or [{"url": "/"}]
        self._routes: list[dict[str, Any]] = []
        self._schemas: dict[str, Any] = {}
        self._spec: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Route registration
    # ------------------------------------------------------------------

    def add_route(self, route_meta: dict[str, Any]) -> None:
        """Register a single route's metadata for spec generation.

        Args:
            route_meta: Dictionary produced by the route decorator with keys
                ``method``, ``path``, ``response``, ``status``, ``tags``,
                ``summary``, ``deprecated``, and optionally ``body``.
        """
        self._routes.append(route_meta)
        self._spec = None  # invalidate cache

    # ------------------------------------------------------------------
    # Spec generation
    # ------------------------------------------------------------------

    def generate(self) -> dict[str, Any]:
        """Return the full OpenAPI 3.1 spec as a plain dictionary.

        The result is cached; call :meth:`invalidate` to force regeneration.
        """
        if self._spec is not None:
            return self._spec

        paths: dict[str, Any] = {}
        components_schemas: dict[str, Any] = {}

        for route in self._routes:
            path = self._convert_path(route.get("path", "/"))
            method = route.get("method", "GET").lower()

            operation: dict[str, Any] = {
                "summary": route.get("summary", ""),
                "operationId": route.get("operation_id", ""),
                "tags": route.get("tags", []),
                "deprecated": route.get("deprecated", False),
                "parameters": [],
                "responses": {},
            }

            # Path / query parameters
            for param in route.get("parameters", []):
                operation["parameters"].append(param)

            # Request body
            body_schema = route.get("body")
            if body_schema is not None and inspect.isclass(body_schema) and issubclass(
                body_schema, BaseModel
            ):
                schema_name = body_schema.__name__
                components_schemas[schema_name] = body_schema.model_json_schema()
                operation["requestBody"] = {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                        }
                    },
                }

            # Response schema
            status_code = str(route.get("status", 200))
            response_schema = route.get("response")
            if response_schema is not None and inspect.isclass(
                response_schema
            ) and issubclass(response_schema, BaseModel):
                resp_name = response_schema.__name__
                components_schemas[resp_name] = response_schema.model_json_schema()
                operation["responses"][status_code] = {
                    "description": "Successful Response",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{resp_name}"}
                        }
                    },
                }
            else:
                operation["responses"][status_code] = {
                    "description": "Successful Response"
                }

            # 422 Unprocessable Entity for all routes
            operation["responses"]["422"] = {
                "description": "Validation Error",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/HTTPValidationError"}
                    }
                },
            }

            paths.setdefault(path, {})[method] = operation

        # Validation error schemas
        components_schemas["HTTPValidationError"] = {
            "type": "object",
            "properties": {
                "detail": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/ValidationError"},
                }
            },
        }
        components_schemas["ValidationError"] = {
            "type": "object",
            "properties": {
                "loc": {
                    "type": "array",
                    "items": {"anyOf": [{"type": "string"}, {"type": "integer"}]},
                },
                "msg": {"type": "string"},
                "type": {"type": "string"},
            },
            "required": ["loc", "msg", "type"],
        }

        self._spec = {
            "openapi": "3.1.0",
            "info": {
                "title": self.title,
                "version": self.version,
                "description": self.description,
            },
            "servers": self.servers,
            "paths": paths,
            "components": {"schemas": components_schemas},
        }
        return self._spec

    def invalidate(self) -> None:
        """Clear the cached spec so the next call to :meth:`generate` rebuilds it."""
        self._spec = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _convert_path(path: str) -> str:
        """Convert Starlette-style ``{param}`` paths to OpenAPI ``{param}`` format.

        Starlette uses ``{param}`` which is already compatible with OpenAPI,
        but this method is here for any future conversion needs.
        """
        return path

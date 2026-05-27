"""Base schema classes for the Aura framework."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class Schema(BaseModel):
    """
    Base schema for all Aura schemas (request and response).

    Configures Pydantic v2 with sensible defaults:
    - ``from_attributes=True``: allows creating from ORM objects.
    - ``populate_by_name=True``: allows using field name alongside alias.
    - ``str_strip_whitespace=True``: automatically strips leading/trailing spaces.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ResponseSchema(Schema):
    """
    Base schema for response payloads.

    Extends :class:`Schema` with no additional behaviour but provides
    a semantic distinction between request and response types, which the
    OpenAPI generator uses to produce accurate response schemas.
    """

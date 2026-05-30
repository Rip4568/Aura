"""Parameter extractor annotations for Aura route handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Marker classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BodyMarker:
    """Marker indicating a parameter should be populated from the request body.

    Attach via ``Annotated``::

        async def create_user(body: Annotated[UserSchema, BodyMarker()]) -> ...:
            ...

    The :class:`~aura.core.pipeline.RequestPipeline` reads the JSON body
    and validates it against the annotated type using Pydantic.
    """

    alias: str | None = field(default=None)
    embed: bool = field(default=False)


@dataclass(frozen=True)
class QueryMarker:
    """Marker indicating a parameter should be extracted from the query string.

    Attach via ``Annotated``::

        async def list_users(
            page: Annotated[int, QueryMarker()],
        ) -> ...:
            ...
    """

    alias: str | None = field(default=None)
    default: Any = field(default=None)
    required: bool = field(default=False)


@dataclass(frozen=True)
class ParamMarker:
    """Marker indicating a parameter should be extracted from the URL path.

    Attach via ``Annotated``::

        @get("/users/{user_id}")
        async def get_user(
            user_id: Annotated[int, ParamMarker()],
        ) -> ...:
            ...
    """

    alias: str | None = field(default=None)


@dataclass(frozen=True)
class HeaderMarker:
    """Marker indicating a parameter should be extracted from a request header.

    Attach via ``Annotated``::

        async def secured(
            auth: Annotated[str, HeaderMarker(alias="Authorization")],
        ) -> ...:
            ...
    """

    alias: str | None = field(default=None)
    convert_underscores: bool = field(default=True)


@dataclass(frozen=True)
class CookieMarker:
    """Marker indicating a parameter should be extracted from a request cookie.

    Attach via ``Annotated``::

        async def profile(
            session: Annotated[str, CookieMarker(alias="session_id")],
        ) -> ...:
            ...
    """

    alias: str | None = field(default=None)


# ---------------------------------------------------------------------------
# Public type aliases  (Body[T], Query[T], etc.)
# ---------------------------------------------------------------------------

# These are *not* real generic aliases at runtime — they are intended to be
# used as Annotated[T, BodyMarker()] shorthand via the module-level helpers
# defined below.  Full generic support requires Python 3.12+ TypeAliasType.
#
# Usage:
#   from aura import Body
#   async def handler(data: Body[CreateUserSchema]) -> ...: ...
#
# At runtime, ``Body[T]`` becomes ``Annotated[T, BodyMarker()]``.

from typing import Annotated  # noqa: E402 (after dataclass definitions)


class _AnnotatedAlias(Generic[T]):
    """Descriptor that allows ``Body[T]`` syntax to produce ``Annotated[T, Marker()]``."""

    def __init__(self, marker_cls: type) -> None:
        self._marker_cls = marker_cls

    def __class_getitem__(cls, item: Any) -> Any:
        return item  # fallback — real magic is in __getitem__

    def __getitem__(self, item: Any) -> Any:
        return Annotated[item, self._marker_cls()]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._marker_cls(*args, **kwargs)


Body: _AnnotatedAlias[Any] = _AnnotatedAlias(BodyMarker)
"""Type alias helper — ``Body[T]`` → ``Annotated[T, BodyMarker()]``."""

Query: _AnnotatedAlias[Any] = _AnnotatedAlias(QueryMarker)
"""Type alias helper — ``Query[T]`` → ``Annotated[T, QueryMarker()]``."""

Param: _AnnotatedAlias[Any] = _AnnotatedAlias(ParamMarker)
"""Type alias helper — ``Param[T]`` → ``Annotated[T, ParamMarker()]``."""

Header: _AnnotatedAlias[Any] = _AnnotatedAlias(HeaderMarker)
"""Type alias helper — ``Header[T]`` → ``Annotated[T, HeaderMarker()]``."""

Cookie: _AnnotatedAlias[Any] = _AnnotatedAlias(CookieMarker)
"""Type alias helper — ``Cookie[T]`` → ``Annotated[T, CookieMarker()]``."""


@dataclass(frozen=True)
class FormDataMarker:
    """Marker para injetar AuraForm preenchido com dados do request.

    Aceita JSON, multipart/form-data e x-www-form-urlencoded.
    Session SQLAlchemy é obtida de request.state.db_session se disponível.

    Attach via ``Annotated``::

        async def create_user(
            form: Annotated[UserForm, FormDataMarker()],
        ) -> ...:
            ...
    """

    pass


FormData: _AnnotatedAlias[Any] = _AnnotatedAlias(FormDataMarker)
"""Type alias helper — ``FormData[T]`` → ``Annotated[T, FormDataMarker()]``."""

"""Aura request wrapper."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request


class AuraRequest(Request):
    """
    Extended Starlette :class:`~starlette.requests.Request` with Aura-specific
    helpers.

    Adds:
    - ``state`` attribute access helpers.
    - ``user`` property for the authenticated user (set by auth middleware).
    - ``container`` property for the per-request DI scope.

    This class is a thin extension — the standard Starlette ``Request`` API
    is fully available.
    """

    @property
    def user(self) -> Any:
        """Return the authenticated user object attached by auth middleware.

        Returns ``None`` if no authentication middleware has populated the
        state.
        """
        return getattr(self.state, "user", None)

    @user.setter
    def user(self, value: Any) -> None:
        """Attach an authenticated user object to the request state.

        Args:
            value: The user object (e.g. a Pydantic model instance).
        """
        self.state.user = value

    @property
    def container(self) -> Any:
        """Return the per-request DI container scope (if set by middleware).

        Returns ``None`` if no DI scope middleware is active.
        """
        return getattr(self.state, "container", None)

    @container.setter
    def container(self, value: Any) -> None:
        """Attach a scoped DI container to the request.

        Args:
            value: A :class:`~aura.di.container.DIContainer` child scope.
        """
        self.state.container = value

    async def json_validated(self, schema: type[Any]) -> Any:
        """Parse the request body as JSON and validate it with *schema*.

        Args:
            schema: A Pydantic model class to validate against.

        Returns:
            A validated instance of *schema*.

        Raises:
            :class:`~aura.exceptions.http.BadRequestException`: If the body
                is not valid JSON.
            :class:`pydantic.ValidationError`: If validation fails.
        """
        from aura.exceptions.http import BadRequestException

        try:
            data = await self.json()
        except Exception as exc:
            raise BadRequestException("Invalid JSON body") from exc
        return schema.model_validate(data)

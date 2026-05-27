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
    - ``htmx`` property — parsed htmx request headers.

    This class is a thin extension — the standard Starlette ``Request`` API
    is fully available.
    """

    @property
    def htmx(self) -> Any:
        """Return parsed htmx request headers as an :class:`~aura.templates.htmx.HtmxInfo`.

        Use this to detect htmx requests and return partial HTML fragments::

            @get("/users")
            async def list_users(self, request: AuraRequest) -> HtmlResponse:
                ctx = UserListContext(users=await self.service.list())
                if request.htmx.is_htmx:
                    return await render("partials/user_rows.html", ctx)
                return await render("users/list.html", ctx)

        Returns:
            :class:`~aura.templates.htmx.HtmxInfo` with parsed headers.
        """
        if not hasattr(self.state, "_htmx"):
            try:
                from aura.templates.htmx import HtmxInfo
                self.state._htmx = HtmxInfo.from_headers(self.headers)
            except ImportError:
                # Templates not installed — return a falsy stub
                class _NoHtmx:
                    is_htmx = False
                self.state._htmx = _NoHtmx()
        return self.state._htmx

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

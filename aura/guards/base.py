"""Base guard class for the Aura framework."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.requests import Request


class Guard(ABC):
    """
    Abstract base class for request authorization guards.

    Guards are evaluated before the route handler is called.  When
    :meth:`can_activate` returns ``False``, :meth:`on_denied` is invoked
    which raises a :class:`~aura.exceptions.http.ForbiddenException` by
    default.

    Subclass and implement :meth:`can_activate` to create custom guards:

    .. code-block:: python

        class AdminGuard(Guard):
            async def can_activate(self, request: Request) -> bool:
                return request.headers.get("X-Admin-Token") == "secret"

    Guards can be applied globally (on the :class:`~aura.core.app.Aura`
    instance), per-module, or per-route using the ``guards`` parameter of
    route decorators.
    """

    @abstractmethod
    async def can_activate(self, request: Request) -> bool:
        """
        Determine whether the request is allowed to proceed.

        Args:
            request: The incoming HTTP request.

        Returns:
            ``True`` to allow the request; ``False`` to deny it.
        """
        ...

    async def on_denied(self, request: Request) -> None:
        """
        Called when :meth:`can_activate` returns ``False``.

        The default implementation raises
        :class:`~aura.exceptions.http.ForbiddenException`.  Override this
        method to raise a different exception (e.g. 401) or to perform
        additional logging.

        Args:
            request: The incoming HTTP request.

        Raises:
            :class:`~aura.exceptions.http.ForbiddenException`: Always, unless
                overridden.
        """
        from aura.exceptions.http import ForbiddenException

        raise ForbiddenException()

    def openapi_security_scheme_name(self) -> str | None:
        """Return the OpenAPI security scheme name, or ``None`` if not applicable."""
        return None

    def openapi_security_scheme(self) -> dict[str, Any] | None:
        """Return the OpenAPI ``components.securitySchemes`` entry for this guard."""
        return None

    def openapi_security_requirement(self) -> dict[str, list[str]] | None:
        """Return the OpenAPI operation ``security`` requirement for this guard."""
        return None

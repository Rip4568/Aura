"""Render shortcuts — the ``render()`` and ``render_string()`` functions.

These are the primary API for rendering templates inside route handlers.
The engine is resolved from the application context so you never need to
pass it explicitly.

Usage::

    from aura.templates import render

    class UserController:
        @html("/users")
        async def list_users(self) -> HtmlResponse:
            users = await self.service.list()
            return await render("users/list.html", UserListContext(
                users=users,
                total=len(users),
            ))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast  # noqa: F401

if TYPE_CHECKING:
    from aura.templates.context import TemplateContext
    from aura.templates.response import HtmlResponse

# Module-level engine reference — set by AuraTemplateModule on startup.
_engine: Any = None


def _get_engine() -> Any:
    """Return the global template engine, raising if not configured."""
    if _engine is None:
        raise RuntimeError(
            "No template engine configured. "
            "Add AuraTemplateModule to your app:\n\n"
            "    from aura.templates import AuraTemplateModule\n"
            "    app = Aura(modules=[AuraTemplateModule.for_root('templates'), ...])"
        )
    return _engine


def set_engine(engine: Any) -> None:
    """Set the global template engine.

    Called automatically by :class:`AuraTemplateModule` on startup.

    Args:
        engine: An :class:`~aura.templates.engine.AuraTemplateEngine` instance.
    """
    global _engine
    _engine = engine


async def render(
    template_name: str,
    context: TemplateContext | dict[str, Any],
    *,
    status: int = 200,
    headers: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> HtmlResponse:
    """Render a template and return an :class:`~aura.templates.response.HtmlResponse`.

    Args:
        template_name: Template file path relative to the template directory.
        context: A :class:`~aura.templates.context.TemplateContext` (recommended)
            or a plain ``dict``.
        status: HTTP status code for the response (default 200).
        headers: Extra HTTP headers to include in the response.
        extra: Additional variables merged into the template context.

    Returns:
        An :class:`~aura.templates.response.HtmlResponse` ready to return
        from a route handler.

    Example::

        @html("/users", template="users/list.html")
        async def list_users(self) -> HtmlResponse:
            users = await self.service.list()
            return await render("users/list.html", UserListContext(
                users=users,
                total=len(users),
            ))
    """
    from aura.templates.response import HtmlResponse
    engine = _get_engine()
    html_content = await engine.render(template_name, context, extra=extra)
    return HtmlResponse(
        content=html_content,
        status_code=status,
        headers=headers,
    )


async def render_string(
    source: str,
    context: TemplateContext | dict[str, Any],
    *,
    status: int = 200,
) -> HtmlResponse:
    """Render a Jinja2 template from a source string.

    Useful for dynamic templates, email bodies, or testing.

    Args:
        source: Jinja2 template source code.
        context: Template context.
        status: HTTP status code.

    Returns:
        An :class:`~aura.templates.response.HtmlResponse`.
    """
    from aura.templates.response import HtmlResponse
    engine = _get_engine()
    html_content = await engine.render_string(source, context)
    return HtmlResponse(content=html_content, status_code=status)


async def render_to_string(
    template_name: str,
    context: TemplateContext | dict[str, Any],
    *,
    extra: dict[str, Any] | None = None,
) -> str:
    """Render a template and return the raw HTML string (no Response wrapper).

    Useful for email rendering, PDF generation, or embedding in JSON.

    Args:
        template_name: Template file path.
        context: Template context.
        extra: Additional variables.

    Returns:
        Rendered HTML string.
    """
    engine = _get_engine()
    return cast(str, await engine.render(template_name, context, extra=extra))

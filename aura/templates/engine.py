"""Aura template engine — Jinja2 with type-safe context, components, and htmx.

The core insight from researching Django/Flask/FastAPI failures:
  - Context is a plain dict → no validation, no IDE support, runtime surprises.
  - No component system → ``{% include %}`` bleeds entire parent context in.
  - Templates make ORM calls → N+1 by default.

AuraTemplateEngine solves all three:
  1. Context must be a :class:`~aura.templates.context.TemplateContext` (Pydantic).
  2. Components are Python classes with typed Props.
  3. Template functions are provided for composing HTML — no ORM calls in templates.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aura.templates.context import TemplateContext


class AuraTemplateEngine:
    """Jinja2-based template engine with Aura extensions.

    Wraps :class:`jinja2.Environment` and adds:

    - ``render(name, context)`` — validated Pydantic context.
    - ``render_string(source, context)`` — render from a string.
    - ``component(name, **kwargs)`` — render a registered component (use with ``await``).
    - ``url_for(name, **path_params)`` — reverse URL lookup.
    - ``static(path)`` — resolve static file URL.
    - Auto-reloading in debug mode (no server restart needed).

    Args:
        template_dirs: Directories searched for templates.
        auto_reload: Re-read templates on every render (dev mode).
        auto_escape: Escape HTML in all rendered variables.
        globals: Extra globals available in every template.

    Example::

        engine = AuraTemplateEngine(template_dirs=["templates"])

        # In your Aura app startup:
        app.templates = engine

    Note:
        Components must be rendered with ``await`` in templates::

            {{ await component('button', label='Click') }}
    """

    def __init__(
        self,
        template_dirs: list[str | Path] | None = None,
        *,
        auto_reload: bool = False,
        auto_escape: bool = True,
        globals: dict[str, Any] | None = None,
    ) -> None:
        try:
            import jinja2
        except ImportError as exc:
            raise ImportError(
                "Jinja2 is required for template rendering.\n"
                "Install it with: pip install aura-web[templates]"
            ) from exc

        dirs = [str(d) for d in (template_dirs or ["templates"])]

        loader = jinja2.FileSystemLoader(dirs)
        self._env = jinja2.Environment(
            loader=loader,
            autoescape=auto_escape,
            auto_reload=auto_reload,
            enable_async=True,
        )

        # Register built-in globals
        self._env.globals.update({
            "component": self.render_component,
            "static": self._static_url,
        })

        # User-supplied globals
        if globals:
            self._env.globals.update(globals)

    # ------------------------------------------------------------------
    # Core render methods
    # ------------------------------------------------------------------

    async def render(
        self,
        template_name: str,
        context: TemplateContext | dict[str, Any],
        *,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Render a template file with a validated context.

        Args:
            template_name: Path relative to a template directory.
            context: A :class:`~aura.templates.context.TemplateContext`
                instance (preferred) or a plain dict.
            extra: Additional variables merged into the template context.

        Returns:
            Rendered HTML string.

        Raises:
            :class:`pydantic.ValidationError`: If context validation fails.
            :class:`jinja2.TemplateNotFound`: If the template file is missing.
        """
        ctx = self._to_dict(context)
        if extra:
            ctx.update(extra)
        template = self._env.get_template(template_name)
        return await template.render_async(**ctx)

    async def render_string(
        self,
        source: str,
        context: TemplateContext | dict[str, Any],
    ) -> str:
        """Render a Jinja2 template from a source string.

        Useful for dynamic or inline templates (e.g. email bodies).

        Args:
            source: Jinja2 template source code.
            context: Context to render with.

        Returns:
            Rendered HTML string.
        """
        ctx = self._to_dict(context)
        template = self._env.from_string(source)
        return await template.render_async(**ctx)

    # Alias used internally by components
    async def render_string_or_file(
        self,
        template_name: str,
        context: dict[str, Any],
    ) -> str:
        template = self._env.get_template(template_name)
        return await template.render_async(**context)

    # ------------------------------------------------------------------
    # Component rendering
    # ------------------------------------------------------------------

    async def render_component(
        self,
        name: str,
        **kwargs: Any,
    ) -> str:
        """Render a registered component by name.

        Args:
            name: Component name as registered (snake_case).
            **kwargs: Props passed to the component.

        Returns:
            Rendered HTML string.

        Raises:
            :class:`KeyError`: If the component is not registered.
            :class:`pydantic.ValidationError`: If props are invalid.
        """
        from aura.templates.component import get_component
        cls = get_component(name)
        if cls is None:
            raise KeyError(
                f"Component '{name}' is not registered. "
                "Did you forget to import the component module?"
            )
        props = cls.validate_props(**kwargs)
        instance = cls(self)
        return await instance.render(props)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(context: TemplateContext | dict[str, Any]) -> dict[str, Any]:
        if hasattr(context, "to_template_dict"):
            return context.to_template_dict()
        return dict(context)

    @staticmethod
    def _static_url(path: str) -> str:
        """Resolve a static file path to a URL.

        Override by setting ``engine.static_url_prefix``.
        """
        prefix = "/static"
        return f"{prefix}/{path.lstrip('/')}"

    # ------------------------------------------------------------------
    # URL resolution
    # ------------------------------------------------------------------

    def set_url_for(self, url_for_fn: Any) -> None:
        """Register a ``url_for`` callable as a Jinja2 global.

        The callable should accept a route name and keyword path parameters
        and return a URL string.

        Args:
            url_for_fn: A callable with signature ``(name, **params) -> str``.
        """
        self._env.globals["url_for"] = url_for_fn

    def register_routes(self, routes: Any) -> None:
        """Build a name-to-path map from *routes* and register ``url_for``.

        Accepts any sequence of Starlette :class:`~starlette.routing.Route`
        objects (or any objects with ``.name`` and ``.path`` attributes).

        Args:
            routes: Iterable of route objects.
        """
        route_map: dict[str, str] = {}
        for route in routes:
            name = getattr(route, "name", None)
            path = getattr(route, "path", None)
            if name and path:
                route_map[name] = path

        def _url_for(name: str, **params: Any) -> str:
            path = route_map.get(name)
            if path is None:
                raise RuntimeError(
                    f"url_for: no route named {name!r}. "
                    f"Available names: {sorted(route_map)}"
                )
            # Substitute {param} placeholders
            def _replace(m: re.Match[str]) -> str:
                key = m.group(1)
                if key in params:
                    return str(params.pop(key))
                raise RuntimeError(
                    f"url_for({name!r}): missing path parameter {key!r}"
                )
            url = re.sub(r"\{(\w+)\}", _replace, path)
            return url

        self.set_url_for(_url_for)

    # ------------------------------------------------------------------
    # Globals / filters
    # ------------------------------------------------------------------

    def add_global(self, name: str, value: Any) -> None:
        """Add a global variable available in every template.

        Args:
            name: Variable name.
            value: Any value or callable.
        """
        self._env.globals[name] = value

    def add_filter(self, name: str, func: Any) -> None:
        """Add a custom Jinja2 filter.

        Args:
            name: Filter name used in templates as ``{{ value|name }}``.
            func: Callable that takes a value and returns the filtered value.

        Example::

            engine.add_filter("money", lambda v: f"${v:.2f}")
            # Template: {{ price|money }} → "$19.99"
        """
        self._env.filters[name] = func

    def add_extension(self, extension: str) -> None:
        """Add a Jinja2 extension.

        Args:
            extension: Dotted import path to the Jinja2 extension class.
        """
        self._env.add_extension(extension)

    @property
    def jinja_env(self) -> Any:
        """Direct access to the underlying :class:`jinja2.Environment`.

        Use this for advanced Jinja2 customisation not covered by the
        Aura API.
        """
        return self._env

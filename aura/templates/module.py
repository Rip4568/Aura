"""AuraTemplateModule — plug the template engine into an Aura application.

Usage::

    from aura import Aura
    from aura.templates import AuraTemplateModule

    app = Aura(
        modules=[
            AuraTemplateModule.for_root("templates"),
            UserModule,
        ]
    )

This registers the :class:`~aura.templates.engine.AuraTemplateEngine` in the
DI container and sets the global shortcut used by :func:`~aura.templates.render`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class AuraTemplateModule:
    """Factory for the Aura template module.

    Use :meth:`for_root` to configure and return the module class ready to
    be passed to ``Aura(modules=[...])``.

    Args:
        template_dirs: Template directories to search.
        auto_reload: Reload templates on file change (default: True in debug).
        auto_escape: HTML-escape all variables (default: True).
        globals: Extra globals available in all templates.
        filters: Custom Jinja2 filters (``name → callable``).
        static_url_prefix: URL prefix for the ``static()`` template helper.
    """

    @classmethod
    def for_root(
        cls,
        *template_dirs: str | Path,
        auto_reload: bool | None = None,
        auto_escape: bool = True,
        globals: dict[str, Any] | None = None,
        filters: dict[str, Any] | None = None,
        static_url_prefix: str = "/static",
    ) -> type:
        """Create and return the template module class.

        Args:
            *template_dirs: One or more template directory paths.
            auto_reload: Re-read templates on disk changes.
                Defaults to ``True`` when the app is in debug mode.
            auto_escape: Escape HTML in all template variables.
            globals: Extra template globals.
            filters: Extra Jinja2 filters.
            static_url_prefix: URL prefix for static files.

        Returns:
            A module class suitable for ``Aura(modules=[...])``.
        """
        dirs = list(template_dirs) or ["templates"]
        _auto_reload = auto_reload
        _auto_escape = auto_escape
        _globals = globals or {}
        _filters = filters or {}
        _static_prefix = static_url_prefix

        class _TemplateModuleClass:
            """Dynamically created template module."""

            __aura_module__ = type("ModuleMetadata", (), {
                "imports": [],
                "providers": [],
                "controllers": [],
                "exports": [],
                "prefix": "",
                "tags": [],
                "guards": [],
            })()

            @staticmethod
            async def on_startup(container: Any, debug: bool = False) -> None:
                from aura.templates.engine import AuraTemplateEngine
                from aura.templates.shortcuts import set_engine

                reload = _auto_reload if _auto_reload is not None else debug
                engine = AuraTemplateEngine(
                    template_dirs=dirs,
                    auto_reload=reload,
                    auto_escape=_auto_escape,
                    globals=_globals,
                )

                # Apply filters
                for name, fn in _filters.items():
                    engine.add_filter(name, fn)

                # Override static URL prefix
                engine._env.globals["static"] = (
                    lambda path, _prefix=_static_prefix: f"{_prefix}/{path.lstrip('/')}"
                )

                # Register engine in DI container and global shortcut
                container.register_instance(AuraTemplateEngine, engine)
                set_engine(engine)

        _TemplateModuleClass.__name__ = "AuraTemplateModule"
        _TemplateModuleClass.__qualname__ = "AuraTemplateModule"
        return _TemplateModuleClass

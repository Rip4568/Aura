"""Server-side component system for Aura templates.

The Problem with Django/Jinja2 includes
----------------------------------------
Django's ``{% include %}`` and Jinja2's ``{% include %}`` pass the *entire*
parent context to the included template by default.  There's no contract
for what the sub-template expects — any variable could be there or not.

Aura Components solve this with a class-based system where:
- **Props** are a :class:`~aura.templates.context.TemplateContext` (Pydantic model)
  — validated before render, IDE-visible, spec-driven.
- The component declares exactly what it needs, nothing implicit bleeds in.
- Components are **testable in isolation** — just instantiate with Props and
  call ``render()``, no HTTP request needed.

Usage
-----
Define the component::

    # components/user_card.py
    from aura.templates.component import Component
    from aura.templates.context import TemplateContext

    class UserCardProps(TemplateContext):
        user: UserResponse
        show_email: bool = False
        highlight: bool = False

    class UserCard(Component):
        template = "components/user_card.html"
        Props = UserCardProps

Use in a Jinja2 template::

    {{ component("user_card", user=user, show_email=True) }}

Or in Python (useful for tests)::

    html = await UserCard(engine).render(UserCardProps(user=user))
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast  # noqa: F401

if TYPE_CHECKING:
    from aura.templates.context import TemplateContext
    from aura.templates.engine import AuraTemplateEngine


# Global registry: template_name → Component class
_COMPONENT_REGISTRY: dict[str, type[Component]] = {}


def register_component(name: str, component_cls: type[Component]) -> None:
    """Register a component class under a name for template use.

    Args:
        name: Short name used in ``{{ component("name", ...) }}`` calls.
        component_cls: The :class:`Component` subclass.
    """
    _COMPONENT_REGISTRY[name] = component_cls


def get_component(name: str) -> type[Component] | None:
    """Look up a registered component by name.

    Args:
        name: Component name.

    Returns:
        The component class, or ``None`` if not registered.
    """
    return _COMPONENT_REGISTRY.get(name)


class ComponentMeta(type):
    """Metaclass that auto-registers Component subclasses."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ) -> ComponentMeta:
        cls = super().__new__(mcs, name, bases, namespace)
        # Auto-register if the class has a 'name' attribute or derive from class name
        if bases and hasattr(cls, "template") and cls.template:
            component_name = getattr(cls, "name", None) or _class_to_name(name)
            register_component(component_name, cast(type["Component"], cls))
        return cls


def _class_to_name(class_name: str) -> str:
    """Convert CamelCase class name to snake_case component name.

    Example: ``UserCard`` → ``user_card``
    """
    import re
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", class_name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


class Component(metaclass=ComponentMeta):
    """Base class for Aura server-side components.

    Subclass and set ``template`` (path to Jinja2 template) and optionally
    ``Props`` (a :class:`~aura.templates.context.TemplateContext` subclass).

    Example::

        class AlertProps(TemplateContext):
            message: str
            type: Literal["info", "warning", "error"] = "info"
            dismissible: bool = True

        class Alert(Component):
            template = "components/alert.html"
            Props = AlertProps
            name = "alert"  # optional override; default: "alert" from class name

    Args:
        engine: The :class:`~aura.templates.engine.AuraTemplateEngine` instance
            used to render the template.
    """

    template: str = ""
    Props: type[TemplateContext] | None = None
    name: str = ""  # override auto-derived name if needed

    def __init__(self, engine: AuraTemplateEngine) -> None:
        self._engine = engine

    async def render(self, props: TemplateContext | dict[str, Any]) -> str:
        """Render the component with the given props.

        Args:
            props: A :class:`~aura.templates.context.TemplateContext` instance
                or a plain dict.

        Returns:
            Rendered HTML string.
        """
        if hasattr(props, "to_template_dict"):
            context = props.to_template_dict()
        else:
            context = dict(props)
        return await self._engine.render_string_or_file(self.template, context)

    @classmethod
    def validate_props(cls, **kwargs: Any) -> TemplateContext:
        """Validate keyword arguments against the Props schema.

        Args:
            **kwargs: Raw props values.

        Returns:
            A validated Props instance.

        Raises:
            :class:`pydantic.ValidationError` if props are invalid.
        """
        if cls.Props is None:
            from aura.templates.context import TemplateContext
            return TemplateContext.model_validate(kwargs)
        return cls.Props.model_validate(kwargs)

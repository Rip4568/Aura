"""Type-safe template context using Pydantic models.

The core problem with Django/Flask templates is that context is a plain dict —
no validation, no IDE autocomplete, no spec. If you forget a field or pass the
wrong type, you get a silent None or a cryptic template error at runtime.

TemplateContext solves this: it is a Pydantic model. The spec of what a
template *expects* is declared in Python, validated before rendering, and fully
visible to IDEs and AI assistants.
"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict

from aura.schema.base import Schema


class TemplateContext(Schema):
    """Base class for all template contexts.

    Subclass this to define the typed context your template expects.
    Pydantic validates all fields before the template is rendered, so
    template errors become Python errors caught at the boundary — not
    cryptic ``{{ variable }}`` failures inside HTML.

    Example::

        class UserListContext(TemplateContext):
            title: str
            users: list[UserResponse]
            total: int
            page: int = 1
            page_size: int = 20

        # In your controller:
        return render("users/list.html", UserListContext(
            title="All Users",
            users=users,
            total=total,
        ))

    The context is converted to a ``dict`` (via :meth:`to_template_dict`) before
    being passed to Jinja2, so template syntax is identical to plain dicts.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
        # Allow arbitrary types (e.g. ORM model instances in context)
        arbitrary_types_allowed=True,
    )

    def to_template_dict(self) -> dict[str, Any]:
        """Convert context to a dict suitable for Jinja2 rendering.

        Pydantic models nested inside the context are also converted so
        templates can access ``{{ user.name }}`` instead of ``{{ user['name'] }}``.

        Returns:
            Flat dict with all context values, nested models serialised.
        """
        return self.model_dump(mode="python")

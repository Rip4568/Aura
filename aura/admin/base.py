from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from aura.orm.base import AuraModel

if TYPE_CHECKING:
    pass


class ModelAdmin:
    """Base class for custom administrative representation of a model."""

    list_display: list[str] = []
    list_filter: list[str] = []
    search_fields: list[str] = []
    actions: list[str] = []

    def __init__(self, model: type[AuraModel]) -> None:
        self.model = model


_registry: dict[type[AuraModel], ModelAdmin] = {}


def register(model: type[AuraModel]) -> Callable[[type[ModelAdmin]], type[ModelAdmin]]:
    """Decorator to register a custom ModelAdmin class for a model.

    Example:
        @register(User)
        class UserAdmin(ModelAdmin):
            list_display = ["id", "name", "email"]
    """
    def decorator(admin_class: type[ModelAdmin]) -> type[ModelAdmin]:
        register_model(model, admin_class)
        return admin_class
    return decorator


def register_model(
    model: type[AuraModel], admin_class: type[ModelAdmin] | None = None
) -> None:
    """Register a model with an optional custom ModelAdmin class.

    If no admin class is provided, the base ModelAdmin is used.
    """
    if admin_class is None:
        admin_class = ModelAdmin
    _registry[model] = admin_class(model)

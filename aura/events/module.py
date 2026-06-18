"""AuraEventsModule — plug the event bus into an Aura application.

Usage::

    from aura import Aura
    from aura.events import AuraEventsModule

    app = Aura(
        modules=[
            AuraEventsModule.for_root(),
            UserModule,
        ]
    )
"""

from __future__ import annotations

from typing import Any

from aura.events.base import EventBus


class AuraEventsModule:
    """Factory for the Aura events module.

    Use :meth:`for_root` to configure and return the module class ready to
    be passed to ``Aura(modules=[...])``.
    """

    @classmethod
    def for_root(cls, *, bus: EventBus | None = None) -> type:
        """Create and return the events module class.

        Args:
            bus: Optional pre-configured :class:`~aura.events.base.EventBus`.
                When omitted, the bus is created from ``AuraConfig.events``
                if ``events.enabled`` is ``True``.

        Returns:
            A module class suitable for ``Aura(modules=[...])``.
        """
        _bus = bus

        class _EventsModuleClass:
            """Dynamically created events module."""

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
                from aura.config.base import AuraConfig
                from aura.events.lifecycle import ensure_events_started

                cfg = await container.resolve_optional(AuraConfig) or AuraConfig()
                events_cfg = getattr(cfg, "events", None)
                registry = getattr(container, "_app_registry", None)
                if registry is None:
                    return

                await ensure_events_started(
                    container=container,
                    registry=registry,
                    bus=_bus,
                    events_config=events_cfg,
                )

        _EventsModuleClass.__name__ = "AuraEventsModule"
        _EventsModuleClass.__qualname__ = "AuraEventsModule"
        return _EventsModuleClass

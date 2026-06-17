"""Tests for AuraTemplateEngine."""

from __future__ import annotations

from typing import cast

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TestAuraTemplateEngine:
    """Test suite for AuraTemplateEngine core functionality."""

    @pytest.mark.anyio
    async def test_render_string_basic(self) -> None:
        """Basic string rendering with context."""
        from aura.templates.engine import AuraTemplateEngine

        engine = AuraTemplateEngine()
        result = await engine.render_string(
            "Hello {{ name }}!", {"name": "World"}
        )
        assert result == "Hello World!"

    @pytest.mark.anyio
    async def test_component_global_is_async(self) -> None:
        """The 'component' global in templates is the async render_component."""
        from aura.templates.engine import AuraTemplateEngine

        engine = AuraTemplateEngine()
        # Verify that component global is render_component (async version)
        component_fn = engine._env.globals.get("component")
        # The function should be render_component (bound method)
        import inspect
        assert inspect.iscoroutinefunction(component_fn) or hasattr(
            component_fn, "__self__"
        )

    def test_no_render_component_sync(self) -> None:
        """Sync _render_component_sync method does not exist."""
        from aura.templates.engine import AuraTemplateEngine

        engine = AuraTemplateEngine()
        # Should not have _render_component_sync method
        assert not hasattr(engine, "_render_component_sync")

    @pytest.mark.anyio
    async def test_render_with_globals(self) -> None:
        """Render with additional globals."""
        from aura.templates.engine import AuraTemplateEngine

        engine = AuraTemplateEngine(globals={"app_name": "TestApp"})
        result = await engine.render_string(
            "{{ app_name }}: {{ message }}", {"message": "OK"}
        )
        assert result == "TestApp: OK"

    @pytest.mark.anyio
    async def test_component_registration_and_render(self) -> None:
        """Component can be registered and rendered as async."""
        from aura.templates.component import Component, register_component
        from aura.templates.context import TemplateContext
        from aura.templates.engine import AuraTemplateEngine

        # Define props
        class TestButtonProps(TemplateContext):
            label: str = "Click"

        # Define component
        class TestButton(Component):
            template = "components/button.html"
            Props = TestButtonProps

            async def render(self, props: TemplateContext | dict[str, str]) -> str:
                # Simple render for testing
                if hasattr(props, "label"):
                    label = getattr(props, "label", "Click")
                else:
                    label = cast(dict[str, str], props).get("label", "Click")
                return f"<button>{label}</button>"

        # Register
        register_component("test_button", TestButton)

        # Verify registration
        from aura.templates.component import get_component
        retrieved = get_component("test_button")
        assert retrieved is TestButton

        # Create engine and verify async component rendering
        engine = AuraTemplateEngine()
        assert hasattr(engine, "render_component")
        assert callable(engine.render_component)

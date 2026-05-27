"""Aura template system — type-safe HTML rendering with htmx support.

Quick start::

    from aura import Aura
    from aura.templates import (
        AuraTemplateModule,
        TemplateContext,
        HtmlResponse,
        Component,
        render,
        html,
    )

    # 1. Define the context (spec for what the template expects)
    class HomeContext(TemplateContext):
        title: str
        user_count: int

    # 2. Render in a controller
    class HomeController:
        @html("/")
        async def home(self) -> HtmlResponse:
            return await render("home.html", HomeContext(
                title="Dashboard",
                user_count=42,
            ))

    # 3. Register the template module
    app = Aura(
        modules=[
            AuraTemplateModule.for_root("templates"),
            ...
        ]
    )
"""

from aura.templates.context import TemplateContext
from aura.templates.response import HtmlResponse
from aura.templates.engine import AuraTemplateEngine
from aura.templates.component import Component
from aura.templates.htmx import HtmxInfo, HtmxResponseHeaders
from aura.templates.shortcuts import render, render_string, render_to_string
from aura.templates.decorators import html, sse
from aura.templates.module import AuraTemplateModule

__all__ = [
    # Context
    "TemplateContext",
    # Response
    "HtmlResponse",
    # Engine
    "AuraTemplateEngine",
    # Components
    "Component",
    # htmx
    "HtmxInfo",
    "HtmxResponseHeaders",
    # Shortcuts
    "render",
    "render_string",
    "render_to_string",
    # Decorators
    "html",
    "sse",
    # Module
    "AuraTemplateModule",
]

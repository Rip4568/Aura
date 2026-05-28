"""
Aura Framework — Modern, async-first, type-safe Python web framework.

Design principles:
- Spec-Driven Development (SDD): the spec is the source of truth
- Async-first: ASGI core with sync support via anyio
- Type-safe: Pydantic v2 throughout
- Modular: NestJS-inspired module system
- AI-friendly: designed for AI-guided development

Quick start::

    from aura import Aura, Module, get, Body, Schema

    class UserSchema(Schema):
        name: str
        email: str

    class UserController:
        @get("/users", response=UserSchema)
        async def list_users(self) -> list[UserSchema]:
            return []

    @Module(controllers=[UserController])
    class UserModule:
        pass

    app = Aura(modules=[UserModule], title="My API")
"""

from aura.config.base import AuraConfig
from aura.core.app import Aura
from aura.core.request import AuraRequest
from aura.core.response import AuraResponse, created, no_content, ok, redirect
from aura.di.container import DIContainer, Lifetime
from aura.di.decorators import inject, injectable
from aura.exceptions.http import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    HTTPException,
    InternalServerException,
    NotFoundException,
    UnauthorizedException,
    UnprocessableEntityException,
)
from aura.guards.base import Guard
from aura.modules.base import Module
from aura.routing.decorators import delete, get, patch, post, put, ws
from aura.routing.params import Body, Cookie, Header, Param, Query
from aura.routing.router import Router
from aura.schema.base import ResponseSchema, Schema

# ORM (optional — requires aura-web[sqlalchemy])
try:
    from aura.orm import AuraModel, DatabaseManager, Page, Repository, db
except ImportError:
    pass

# JWT Guard (optional — requires aura-web[jwt])
try:
    from aura.guards.jwt import JWTGuard
except ImportError:
    pass

# Per-route rate-limit guard (no external deps)
from aura.guards.rate_limit import RateLimitGuard

# Session middleware (optional — requires aura-web[session])
try:
    from aura.middleware.session import SessionMiddleware
except ImportError:
    pass

# Templates (optional — requires aura-web[templates])
try:
    from aura.templates import (  # noqa: F401
        AuraTemplateEngine,
        AuraTemplateModule,
        Component,
        HtmlResponse,
        HtmxInfo,
        TemplateContext,
        html,
        render,
        render_string,
        render_to_string,
        sse,
    )
except ImportError:
    pass  # Jinja2 not installed — templates disabled

__version__ = "0.2.0"

__all__ = [
    # Application
    "Aura",
    # Modules
    "Module",
    # Routing
    "Router",
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "ws",
    # Parameter extractors
    "Body",
    "Param",
    "Query",
    "Header",
    "Cookie",
    # Schemas
    "Schema",
    "ResponseSchema",
    # DI
    "injectable",
    "inject",
    "DIContainer",
    "Lifetime",
    # Guards
    "Guard",
    "RateLimitGuard",
    "JWTGuard",
    "SessionMiddleware",
    # Exceptions
    "HTTPException",
    "BadRequestException",
    "UnauthorizedException",
    "ForbiddenException",
    "NotFoundException",
    "ConflictException",
    "UnprocessableEntityException",
    "InternalServerException",
    # Config
    "AuraConfig",
    # ORM (optional)
    "AuraModel",
    "Repository",
    "Page",
    "DatabaseManager",
    "db",
    # Response helpers
    "AuraResponse",
    "ok",
    "created",
    "no_content",
    "redirect",
    # Request
    "AuraRequest",
]

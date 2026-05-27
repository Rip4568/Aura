# 🌌 Aura Framework

**Modern, async-first, type-safe Python web framework with Schema-Driven Development (SDD) support.**

Aura resolves the pain points of Django, FastAPI, and Flask by providing:

- **Async-first** — ASGI core with genuine async ORM (SQLAlchemy 2.x)
- **Type-safe** — Pydantic v2 throughout, mypy strict mode
- **SDD** — Schema-Driven Development: schemas are the source of truth
- **Modular** — NestJS-inspired module system with DI container
- **Jobs built-in** — Native async task queue (SAQ/Taskiq), no Celery
- **Config as code** — `aura.toml` replaces `settings.py`
- **AI-friendly** — Designed for AI-guided development via specs

## Quick Start

```python
from aura import Aura, Module, Schema
from aura.routing.router import Router
from aura.routing.decorators import get, post

router = Router(prefix="/api")

class UserSchema(Schema):
    name: str
    email: str

@router.get("/hello")
async def hello() -> dict:
    return {"message": "Hello from Aura! 🌌"}

@Module(controllers=[router])
class AppModule:
    pass

app = Aura(modules=[AppModule], title="My Aura App")
```

Run: `uvicorn main:app --reload`

## Installation

```bash
pip install aura-framework[uvicorn,orm,saq]
```

## Documentation

- `/docs` — Swagger UI (auto-generated)
- `/redoc` — ReDoc UI (auto-generated)
- `/openapi.json` — OpenAPI 3.1 schema

## License

MIT

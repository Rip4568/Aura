<p align="center">
  <h1 align="center">🌌 Aura Framework</h1>
  <p align="center">
    <strong>O framework Python moderno que você sempre quis.</strong><br/>
    Async nativo · Type-safe · Schema-Driven · Módulos · Jobs integrados
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python" />
    <img src="https://img.shields.io/badge/pydantic-v2-orange?style=flat-square" />
    <img src="https://img.shields.io/badge/async-first-green?style=flat-square" />
    <img src="https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square" />
    <img src="https://img.shields.io/badge/status-alpha-red?style=flat-square" />
  </p>
</p>

---

> **Aura** nasceu da frustração real com o Django, FastAPI e Flask.  
> Frameworks que ou te dão baterias antigas, ou te deixam comprar tudo separado.  
> Aura entrega o melhor dos dois mundos: **opiniões certas nos lugares certos, liberdade onde importa.**

---

## ✨ Por que Aura?

| Problema real | Como outros resolvem | Como Aura resolve |
|---|---|---|
| `settings.py` com 500 linhas | Django: um arquivo global | `aura.toml` modular + config type-safe por seção |
| ORM síncrono em stack async | Django: `sync_to_async()` em todo lugar | SQLAlchemy 2.x async genuíno desde o core |
| Serializers fazem tudo (DRF) | ViewSet + Serializer + Permissions misturados | Schemas (DTOs) separados de Services e Routers |
| Celery complexo, sem async | Celery 5: ainda sem `async def` nativo | `@task(queue="emails")` — async de verdade |
| DI só funciona no HTTP | FastAPI: `Depends()` não roda em jobs/CLI | `DIContainer` funciona em qualquer contexto |
| Typing quebra com mypy | Django: metaclass magic quebra o type checker | Pydantic v2 em todo o framework, mypy strict |
| Sem estrutura de projeto | FastAPI: 82+ boilerplates diferentes | `@Module` NestJS-inspired com DI encapsulado |
| N+1 queries em produção | DRF: serializers aninhados sem select_related | `Repository[T]` com métodos otimizados |

---

## 🚀 Início rápido

```bash
pip install aura-framework[uvicorn]
```

```python
# main.py
from aura import Aura, Module, Schema, injectable
from aura.routing.decorators import get, post
from aura.routing.params import Body, Param

class CreateUserSchema(Schema):
    name: str
    email: str

@injectable
class UserService:
    async def create(self, data: CreateUserSchema) -> dict:
        return {"id": 1, **data.model_dump()}

class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @get("/users")
    async def list_users(self) -> list:
        return await self.service.list_all()

    @post("/users")
    async def create_user(self, body: Body[CreateUserSchema]) -> dict:
        return await self.service.create(body)

@Module(controllers=[UserController], providers=[UserService], prefix="/api")
class UserModule:
    pass

app = Aura(modules=[UserModule], title="Minha API")
```

```bash
uvicorn main:app --reload
# → /docs    (Swagger UI auto-gerado)
# → /redoc   (ReDoc auto-gerado)
```

---

## 📚 Documentação

| Documento | Descrição |
|---|---|
| [Motivação e Comparativo](docs/motivation.md) | Por que Aura existe, dores que resolve |
| [Schemas e Validação](docs/schemas-validation.md) | DTOs, Pydantic v2, validação de dados |
| [ORM e Queries](docs/orm-queries.md) | Repository pattern, CRUD, busca, filtros |
| [Jobs e Workers](docs/jobs-workers.md) | Tasks assíncronas, queues, periodic jobs |
| [Módulos e DI](docs/modules-di.md) | Sistema de módulos, injeção de dependência |
| [Roadmap](docs/roadmap.md) | O que está sendo construído |

---

## ⚡ CLI

```bash
aura new project meu-projeto
aura generate module users
aura run
aura worker
aura migrate make "add users"
```

## 📄 Licença

MIT © Aura Contributors

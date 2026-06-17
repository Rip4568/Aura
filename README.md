<p align="center">
  <h1 align="center">🌌 Aura Framework</h1>
  <p align="center">
    <strong>O framework Python moderno que você sempre quis.</strong><br/>
    Async nativo · Type-safe · Spec-Driven · Módulos · Guards · Jobs · HTML server-rendered
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python" />
    <img src="https://img.shields.io/badge/pydantic-v2-orange?style=flat-square" />
    <img src="https://img.shields.io/badge/pypi-aura--web-purple?style=flat-square" />
    <img src="https://img.shields.io/pypi/v/aura-web?style=flat-square&color=blue" />
    <img src="https://img.shields.io/badge/tests-713%20passing-brightgreen?style=flat-square" />
    <img src="https://img.shields.io/badge/license-MIT-lightgrey?style=flat-square" />
    <img src="https://img.shields.io/badge/status-alpha-red?style=flat-square" />
  </p>
</p>

---

> **Aura** nasceu da frustração real com Django, FastAPI e Flask.  
> Frameworks que ou te dão baterias antigas, ou te deixam comprar tudo separado.  
> Aura entrega o melhor dos dois mundos: **opiniões certas nos lugares certos, liberdade onde importa.**

---

## ✨ Por que Aura?

| Problema real                | Como outros resolvem                                           | Como Aura resolve                                            |
| ---------------------------- | -------------------------------------------------------------- | ------------------------------------------------------------ |
| `settings.py` com 500 linhas | Django: um arquivo global                                      | `aura.toml` modular + config type-safe por seção             |
| ORM síncrono em stack async  | Django: `sync_to_async()` em todo lugar                        | SQLAlchemy 2.x async genuíno desde o core                    |
| Serializers fazem tudo (DRF) | ViewSet + Serializer + Permissions misturados                  | Schemas (DTOs) separados de Services e Controllers           |
| Celery complexo, sem async   | Celery 5: ainda sem `async def` nativo                         | `@task(queue="emails")` — async de verdade                   |
| DI só funciona no HTTP       | FastAPI: `Depends()` não roda em jobs/CLI                      | `DIContainer` funciona em qualquer contexto                  |
| Typing quebra com mypy       | Django: metaclass magic quebra o type checker                  | Pydantic v2 em todo o framework, mypy strict                 |
| Sem estrutura de projeto     | FastAPI: 82+ boilerplates diferentes                           | `@Module` NestJS-inspired com DI encapsulado                 |
| N+1 queries em produção      | DRF: serializers aninhados sem select_related                  | `Repository[T]` com métodos otimizados                       |
| Context dict não tipado      | Django templates: `render(request, "tmpl.html", {"key": val})` | `TemplateContext` (Pydantic) — validado antes de renderizar  |
| Auth manual em cada projeto  | FastAPI: `Depends(get_current_user)` por conta própria         | `JWTGuard` + `RateLimitGuard` + `SessionMiddleware` built-in |

---

## 🚀 Instalação

```bash
# Instalação básica (API REST)
pip install "aura-web[uvicorn]"

# Com suporte a templates HTML (Jinja2)
pip install "aura-web[uvicorn,templates]"

# Com banco de dados
pip install "aura-web[uvicorn,sqlalchemy]"

# Tudo incluído
pip install "aura-web[all]"
```

---

## ⚡ Início rápido

### Projeto novo (CLI)

```bash
# Cria um projeto completo e funcional com um módulo Users pronto
aura new meu-projeto
cd meu_projeto
pip install -e ".[dev]"
aura run --reload
```

Isso gera a estrutura completa:

```
meu_projeto/
├── main.py                      # app = Aura(modules=[UsersModule])
├── aura.toml                    # configuração do servidor
├── pyproject.toml
├── .env.example
├── modules/
│   └── users/
│       ├── schemas.py           # CreateUserDTO, UpdateUserDTO, UserResponse
│       ├── service.py           # @injectable UserService (in-memory, pronto pra usar)
│       ├── controller.py        # CRUD completo: @get @post @put @delete
│       ├── repository.py        # metodos builtins como: create,update, delete, list, bulk_create, bulk_update, bulk_delete
│       ├── model.py             # Definição dos modelos de estrutra de dados do backend.
│       └── module.py            # @Module(providers, controllers, prefix)
└── tests/
    ├── conftest.py              # AsyncClient via ASGITransport
    └── test_users.py            # 7 testes de integração
```

---

## 🔌 API REST com ORM assíncrono

> Django tem ORM mas é síncrono.  
> FastAPI não tem ORM — você conecta SQLAlchemy na mão.  
> Aura tem `AuraModel` + `Repository[T]` + `db.session()` — async nativo, sem gambiarras.

```python
# modules/posts/models.py
from aura.orm import AuraModel, CharField, TextField, BooleanField
from sqlalchemy.orm import Mapped

class Post(AuraModel):
    __tablename__ = "posts"

    title:     Mapped[str]  = CharField(max_length=200)
    body:      Mapped[str]  = TextField()
    published: Mapped[bool] = BooleanField(default=False)
    # id, created_at, updated_at → herdados de AuraModel automaticamente
```

```python
# modules/posts/repository.py
from aura.orm import Repository
from sqlalchemy import select
from .models import Post

class PostRepository(Repository[Post]):
    model = Post

    # Métodos herdados:
    # get, get_or_raise, list, create, update, delete,
    # exists, count, first, bulk_create, bulk_update, bulk_delete, paginate

    async def list_published(self, *, limit: int = 20) -> list[Post]:
        # Recomendado: query fluente estilo Django do Aura (AuraQL)
        return await (
            Post.objects
            .filter(published=True)
            .order_by("-created_at")
            .limit(limit)
            .all()
        )
```

```python
# modules/posts/service.py
from aura import injectable, NotFoundException
from aura.orm import db, Page
from .models import Post
from .repository import PostRepository
from .schemas import CreatePostDTO, UpdatePostDTO

@injectable
class PostService:
    def __init__(self, post_repository: PostRepository) -> None:
        self.repo = post_repository  # Injetado como Singleton pelo container na inicialização

    async def list_posts(self, page: int = 1) -> Page[Post]:
        # A sessão ativa do request HTTP é resolvida de forma transparente
        return await self.repo.paginate(
            page=page, per_page=20, order_by="created_at"
        )

    async def get_post(self, post_id: int) -> Post:
        return await self.repo.get_or_raise(post_id)

    async def create_post(self, data: CreatePostDTO) -> Post:
        return await self.repo.create(**data.model_dump())

    async def transfer_posts(self, from_id: int, to_id: int) -> None:
        """Garante atomicidade (Tudo ou Nada).
        
        As operações executadas dentro da mesma requisição HTTP compartilham a transação principal
        gerenciada automaticamente pelo DatabaseMiddleware. Em caso de falha ou erro, o
        middleware executa o rollback completo garantindo a integridade transacional.
        """
        await self.repo.update(from_id, published=False)
        await self.repo.update(to_id, published=True)

    async def get_dashboard_data(self) -> dict:
        """Busca concorrente em paralelo (equivalente a Promise.all do NodeJS).
        
        O SQLAlchemy impede a execução de múltiplas queries concorrentes usando a MESMA session.
        Para resolver isso, o Aura fornece o helper `db.parallel` que abre sessões
        independentes e gerencia a execução paralela concorrente de forma isolada e segura.
        """
        recent_posts, total_count = await db.parallel(
            lambda s: PostRepository(s).list(limit=5, order_by="created_at"),
            lambda s: PostRepository(s).count()
        )
        return {
            "recent": recent_posts,
            "total": total_count
        }
```


```python
# modules/posts/controller.py
from aura import get, post, put, delete, Body, Query
from aura.orm import Page
from .schemas import CreatePostDTO, UpdatePostDTO, PostResponse
from .service import PostService

class PostsController:
    def __init__(self, service: PostService) -> None:
        self.service = service

    @get("/")
    async def list_posts(self, page: Query[int] = 1) -> Page[PostResponse]:
        # O Aura serializa Page[Post] para Page[PostResponse] de forma ultra-rápida via TypeAdapter!
        return await self.service.list_posts(page)

    @get("/{post_id}")
    async def get_post(self, post_id: int) -> PostResponse:
        # post_id é inferido e convertido para int de forma implícita a partir do path!
        return await self.service.get_post(post_id)

    @post("/", status=201)
    async def create_post(self, body: Body[CreatePostDTO]) -> PostResponse:
        return await self.service.create_post(body)

    @put("/{post_id}")
    async def update_post(
        self,
        post_id: int,
        body: Body[UpdatePostDTO],
    ) -> PostResponse:
        return await self.service.update_post(post_id, body)

    @delete("/{post_id}", status=204)
    async def delete_post(self, post_id: int) -> None:
        await self.service.delete_post(post_id)

```

```python
# modules/posts/module.py
from aura import Module
from .controller import PostsController
from .service import PostService

@Module(providers=[PostService], controllers=[PostsController], prefix="/posts", tags=["Posts"])
class PostsModule:
    pass
```

```python
# main.py
import os
from aura import Aura
from modules.posts.module import PostsModule

# Opção 1: env var — Aura inicializa o pool automaticamente na startup
# export AURA__DATABASE__URL=sqlite+aiosqlite:///./app.db
app = Aura(modules=[PostsModule], title="Blog API", version="1.0.0")

# Opção 2: inicialização manual (mais controle)
# from aura.orm import db
# db.init("sqlite+aiosqlite:///./app.db")
```

```bash
aura run --reload
# GET  /posts/?page=2  → listagem paginada (Page[PostResponse])
# GET  /posts/1        → busca por ID (404 automático se não existir)
# POST /posts/         → cria post
# PUT  /posts/1        → atualiza
# DELETE /posts/1      → remove
# GET  /docs           → Swagger UI auto-gerado
# GET  /health         → { "status": "ok", "version": "1.0.0" }
```

### Database Seeders

O Aura possui suporte nativo para seeding de banco de dados assíncrono com injeção de dependências e proteção para produção.

#### Exemplo de Seeder:

```python
# database/seeders/user_seeder.py
from aura.orm import Seeder
from modules.users.models import User

class UserSeeder(Seeder):
    async def run(self) -> None:
        user = User(name="John Doe", email="john@example.com")
        await self.save(user)  # Salva transparentemente na transação ativa
```

Você pode encadear seeders de forma hierárquica chamando outros sub-seeders recursivamente:

```python
# database/seeders/main_seeder.py
from aura.orm import Seeder
from .user_seeder import UserSeeder

class DatabaseSeeder(Seeder):
    async def run(self) -> None:
        # Executa múltiplos sub-seeders resolvidos via DI
        await self.call([UserSeeder])
```

Para executar seus seeders via CLI:

```bash
# Executa o seeder principal (DatabaseSeeder por padrão)
aura db seed

# Executa um seeder específico
aura db seed --class UserSeeder

# Executa de forma idempotente (pula seeders já registrados em _aura_seeded)
aura db seed --once
```

Confira a [Documentação de Seeders](docs/seeders.md) para detalhes completos de DI, transações e segurança em produção.

### Model Factories & Faker

Aura fornece uma infraestrutura robusta e moderna de **Factories** baseada no padrão Object Factory e integrada de forma nativa com a biblioteca **Faker**. Isso simplifica drasticamente a geração de dados para testes de integração, seeders e ambientes de desenvolvimento local.

#### Definindo uma Fábrica

As fábricas herdam de `Factory` e definem o modelo alvo e os atributos padrão usando o gerador `self.faker`. Relacionamentos são mapeados de forma elegante com `SubFactory`:

```python
from aura.orm import Factory, SubFactory
from .models import User, Post

class UserFactory(Factory[User]):
    model = User

    def definition(self) -> dict:
        return {
            "name": lambda: self.faker.name(),
            "email": lambda: self.faker.unique.email(),
            "active": True,
        }

class PostFactory(Factory[Post]):
    model = Post

    def definition(self) -> dict:
        return {
            "title": lambda: self.faker.sentence(),
            "body": lambda: self.faker.paragraph(),
            "author": SubFactory(UserFactory),  # Relacionamento automático
        }
```

#### Estratégias de Geração

O Aura diferencia explicitamente a geração em memória vs. a persistência no banco de dados para otimizar a velocidade e garantir previsibilidade nos testes:

1. **Geração Síncrona em Memória (Rápida):** Instancia modelos sem tocar no banco de dados.
   ```python
   # Única instância em memória
   post = PostFactory().make(title="Título Customizado")
   
   # Em lote (Batch) em memória
   posts = PostFactory().make_many(5)
   ```

2. **Persistência Assíncrona no Banco (Real):** Salva e commita automaticamente no banco usando a sessão ativa ou abrindo uma nova transação.
   ```python
   # Única instância persistida
   post = await PostFactory().create(title="Título Customizado")
   
   # Em lote (Batch) persistido
   posts = await PostFactory().create_many(5)
   ```

#### Estado Imutável (`.state()`)

Modifique fábricas de forma fluente e segura sem alterar a definição original:

```python
# Cria uma fábrica especializada em posts publicados
published_factory = PostFactory().state(is_published=True)

# Gera os posts publicados
published_posts = await published_factory.create_many(3)
```

> [!NOTE]
> Para uma documentação abrangente sobre estratégias avançadas, controle atômico de sessões sob ContextVars e tratamento de relacionamentos, confira o guia completo de [Model Factories](docs/factories.md).

---

## 🔐 Auth, Guards e Segurança

> **Hardening (v1.2.x):** parâmetros inválidos retornam **422**; `redirect()` aceita só paths relativos; logs de startup redactam secrets; extra `[jwt]` usa **PyJWT**. Ver [ADR-001](docs/decisions/ADR-001-security-hardening.md).

> **Estabilidade (v1.3.x — Wave 3):** `DatabaseMiddleware` fail-fast em falha de init; `RateLimitGuard` com headers `X-RateLimit-*`; `aura worker --burst` funcional com SAQ; templates exigem `await component(...)`. Ver [ADR-002](docs/decisions/ADR-002-async-templates-only.md) e [CHANGELOG](CHANGELOG.md).

> **DX & Observabilidade (v1.4.x — Wave 4):** rate limit com backend Redis para multi-worker; `JWTGuard` expõe `BearerAuth` no Swagger; `Router.tags` faz merge com tags de rota; `RequestLogInterceptor` redacta headers sensíveis. Ver [CHANGELOG](CHANGELOG.md).

> **Contrato & Admin (v1.4.0 — Waves 5–6):** interceptors globais via `Aura(interceptors=[...])`; `UnprocessableEntityException` com corpo 422 estruturado; `ModelForm` no admin; ver [ADR-003](docs/decisions/ADR-003-contract-cleanup.md) e [ADR-004](docs/decisions/ADR-004-admin-modelform.md).

> **Infra & Release (v1.4.0 — Waves 7–8):** CI com Python 3.11/3.13, pre-commit (ruff + mypy), rate limit Redis atômico (Lua), `trusted_proxies` para IP real atrás de proxy, `JWTGuard(require_exp=True)` por padrão, `SessionMiddleware` só reenvia cookie quando a sessão muda. Ver [CHANGELOG](CHANGELOG.md) e `docs/pending.md`.

> **Messaging & Jobs (v1.5.0 — Waves 9–11):** fila de jobs em SQL sem Redis (`AURA__JOBS__BACKEND=database`); `EventBus` com `@on_event`; backends RabbitMQ/Kafka com `@EventPattern`, `@MessagePattern` e `MessagingClient`. Ver [ADR-006](docs/decisions/ADR-006-event-bus.md), [ADR-007](docs/decisions/ADR-007-message-brokers.md) e [CHANGELOG](CHANGELOG.md).

### JWTGuard — autenticação Bearer

Requer `pip install "aura-web[jwt]"` (instala **PyJWT[crypto]**, não `python-jose`).

```python
from aura import get, Module
from aura.guards import JWTGuard

# Aplica em uma rota específica
class UserController:
    @get("/me", guards=[JWTGuard(secret="sua-chave-secreta")])
    async def get_me(self, request: AuraRequest) -> dict:
        return request.state.user  # payload do JWT

# Aplica em todas as rotas do módulo
@Module(
    controllers=[UserController],
    guards=[JWTGuard(secret="sua-chave-secreta")],
    prefix="/users",
)
class UserModule:
    pass
```

```python
# Ou configure uma vez e reutilize em qualquer módulo
jwt = JWTGuard(
    secret="sua-chave-secreta",
    algorithm="HS256",     # padrão
    auto_error=True,       # 401 automático (padrão)
    require_exp=True,      # padrão — rejeita tokens sem claim exp
)

# Tokens de longa duração sem expiração: opt-out explícito
legacy_jwt = JWTGuard(secret="...", require_exp=False)
```

### RateLimitGuard — proteção por rota

```python
from aura import post, Module, Body
from aura.guards import RateLimitGuard

class AuthController:
    @post("/login", guards=[RateLimitGuard(max_requests=5, window_seconds=60)])
    async def login(self, body: Body[LoginDTO]) -> TokenResponse:
        # Máximo 5 tentativas por minuto por IP
        ...
```

Em **429**, o guard retorna headers alinhados ao `RateLimitMiddleware`:

| Header | Significado |
|--------|-------------|
| `X-RateLimit-Limit` | Máximo de requisições na janela |
| `X-RateLimit-Remaining` | `0` quando bloqueado |
| `Retry-After` | Segundos até nova tentativa |

Parâmetro `max_tracked_keys` (padrão `10000`) limita chaves em memória com eviction LRU — útil em rotas públicas com muitos IPs distintos.

### Rate limit distribuído com Redis (v1.4.x)

Em produção com múltiplos workers (`aura run --workers 4`), use `RedisBackend` — contadores distribuídos com script Lua atômico (sem race conditions entre processos):

```python
from aura import Aura
from aura.middleware import RateLimitMiddleware
from aura.middleware.rate_limit_backends import RedisBackend
from starlette.middleware import Middleware

redis_backend = RedisBackend(redis_url="redis://localhost:6379")

app = Aura(
    modules=[...],
    middleware=[
        Middleware(
            RateLimitMiddleware,
            max_requests=100,
            window_seconds=60,
            backend=redis_backend,
        ),
    ],
)
```

O mesmo backend funciona no `RateLimitGuard` por rota:

```python
from aura.guards import RateLimitGuard
from aura.middleware.rate_limit_backends import RedisBackend

login_limit = RateLimitGuard(
    max_requests=5,
    window_seconds=60,
    backend=RedisBackend(redis_url="redis://localhost:6379"),
)
```

Requer `pip install "aura-web[redis]"`. Sem Redis, o padrão continua sendo `MemoryBackend` (adequado para dev e single-process).

### IP real atrás de reverse proxy — `trusted_proxies` (v1.4.0)

Por padrão, `X-Forwarded-For` é **ignorado** (evita spoofing). Informe os IPs dos seus proxies confiáveis:

```python
from aura import Aura
from aura.middleware import RateLimitMiddleware
from starlette.middleware import Middleware

app = Aura(
    modules=[...],
    middleware=[
        Middleware(
            RateLimitMiddleware,
            max_requests=100,
            window_seconds=60,
            trusted_proxies=["10.0.0.1", "127.0.0.1"],  # nginx, traefik, etc.
        ),
    ],
)
```

O mesmo parâmetro existe em `RateLimitGuard` e em `AuraConfig.security.trusted_proxies` (via `aura.toml` ou `AURA__SECURITY__TRUSTED_PROXIES`).

### OpenAPI — `BearerAuth` no Swagger (v1.4.x)

Rotas protegidas por `JWTGuard` expõem automaticamente o esquema `BearerAuth` em `/docs` e `/redoc`:

```python
from aura import get, Module
from aura.guards import JWTGuard

jwt = JWTGuard(secret="sua-chave-secreta")

class UserController:
    @get("/me", guards=[jwt])
    async def get_me(self) -> dict:
        ...

# Tags do Router são mescladas com tags da rota (sem duplicatas):
# Router(prefix="/api", tags=["catalog"]) + @get("/items", tags=["items"])
# → operation.tags == ["catalog", "items"]
```

No Swagger UI, use **Authorize** com `Bearer <token>`.

> **Nota:** o parâmetro é `window_seconds`, não `window`. Mensagens de erro do framework são em **inglês** (corpo JSON e texto plano); a documentação do projeto está em português.

### SessionMiddleware — sessões em cookie

O cookie é assinado, `HttpOnly`, e **só é reenviado quando a sessão é modificada** (não em toda resposta).

```python
from aura import Aura
from aura.middleware import SessionMiddleware  # pip install "aura-web[session]"
from starlette.middleware import Middleware

app = Aura(
    modules=[...],
    middleware=[
        Middleware(SessionMiddleware, secret_key="chave-secreta-longa"),
    ],
)

# Em qualquer controller:
from aura import Body

class CartController:
    @post("/add")
    async def add_item(self, request: AuraRequest, body: Body[ItemDTO]) -> dict:
        cart = request.state.session.get("cart", [])
        cart.append(body.product_id)
        request.state.session["cart"] = cart
        return {"items": len(cart)}

```

### Guard personalizado

```python
from aura import Guard
from starlette.requests import Request

class AdminGuard(Guard):
    async def can_activate(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return user is not None and user.get("role") == "admin"

    async def on_denied(self, request: Request) -> None:
        raise ForbiddenException("Acesso restrito a administradores")
```

### Admin panel — PBKDF2, CSRF, ModelForm e logout seguro

O painel admin (`aura/admin/`) aplica hardening da wave 2 e consolidação da wave 6:

- Senhas verificadas com **PBKDF2-HMAC-SHA256** (`aura/admin/security.py`); hashes legados em texto puro ainda aceitos na migração
- Mutações (create/update/delete via htmx) exigem header `X-CSRF-Token` da sessão
- Logout via **POST** `/admin/logout` (não GET)
- **`ModelForm`:** mapeamento automático de colunas SQLAlchemy → campos `AuraForm` no CRUD admin ([ADR-004](docs/decisions/ADR-004-admin-modelform.md))

Configure credenciais via variáveis de ambiente (`AURA__ADMIN__*`); nunca commite senhas no repositório.

### ORM — delete sem filtro (breaking change)

`QuerySet.delete()` e equivalentes no `Repository` **não** apagam a tabela inteira por padrão:

```python
# Erro — sem filtros
await Post.objects.delete()  # ValueError

# Correto — com filtro ou opt-in explícito
await Post.objects.filter(archived=True).delete()
await Post.objects.delete(allow_unfiltered=True)  # intencional
```

### DatabaseMiddleware — fail-fast (v1.3.x)

Se o banco não inicializar (URL inválida, driver ausente, lazy-init em TestClient), o middleware retorna **500** com corpo acionável em vez de deixar a requisição falhar depois sem sessão:

```
Service Unavailable: Database initialization failed.
Set AURA__DATABASE__URL env var or configure [database] url in aura.toml.
```

Configure antes de subir o app:

```bash
export AURA__DATABASE__URL=sqlite+aiosqlite:///./app.db
# ou em aura.toml: [database] url = "..."
```

### Templates — `await component(...)` (breaking change v1.3.x)

Componentes Jinja2 são assíncronos. Use `await` em cada chamada:

```jinja2
{# Correto (v1.3.0+) #}
{{ await component('user_card', user=user, show_email=True) }}

{% for btn in buttons %}
  {{ await component('button', label=btn) }}
{% endfor %}
```

```diff
- {{ component('button', label='Click') }}
+ {{ await component('button', label='Click') }}
```

Sem `await`, o Jinja2 pode renderizar uma coroutine como texto ou lançar `TemplateRuntimeError`. Migração completa: [ADR-002](docs/decisions/ADR-002-async-templates-only.md).

### Breaking changes — v1.4.0 (Waves 5–8)

| Área | Mudança | Migração |
|------|---------|----------|
| **422** | Erros de validação retornam `{detail: [{loc, msg, type}]}` (formato FastAPI) | Ajuste parsers de cliente; use `UnprocessableEntityException(detail=[...])` para erros customizados |
| **JWT** | `JWTGuard` rejeita tokens **sem** claim `exp` por padrão | Passe `require_exp=False` para tokens legados sem expiração |
| **Session** | Cookie `Set-Cookie` só quando a sessão muda; inclui `HttpOnly` | Se dependia de reenvio em toda resposta, leia sessão sem mutar ou force escrita explícita |
| **ORM** | `delete()` sem filtros exige `allow_unfiltered=True` | Ver seção ORM abaixo — [ADR-001](docs/decisions/ADR-001-security-hardening.md) |
| **JWT dep** | Extra `[jwt]` instala **PyJWT**, não `python-jose` | `pip install "aura-web[jwt]"` |
| **Templates** | `component(...)` exige `await` | `{{ await component(...) }}` — [ADR-002](docs/decisions/ADR-002-async-templates-only.md) |

---

## 🏗️ Estrutura de um módulo

```
modules/
└── posts/
    ├── __init__.py
    ├── models.py        ← AuraModel com __tablename__ e campos
    ├── schemas.py       ← DTOs: CreatePostDTO, UpdatePostDTO, PostResponse
    ├── service.py       ← @injectable PostService (business logic)
    ├── controller.py    ← HTTP handlers (@get, @post, @html, @sse)
    ├── repository.py    ← Repository[Post] (queries customizadas)
    └── module.py        ← @Module(providers, controllers, prefix, tags, guards)
```

Gere um módulo completo com banco de dados:

```bash
aura generate module posts --with-db
# Cria todos os arquivos acima com código funcional (não stubs comentados)
```

---

## 📄 Full-stack com HTML (Jinja2 + htmx)

> `@html` e `@sse` coexistem com `@get`/`@post` no mesmo controller.  
> Use `@get`/`@post` para JSON API. Use `@html` para páginas server-rendered.

```python
from typing import Annotated
from aura import Module
from aura.templates import html, sse, render, TemplateContext, AuraTemplateModule
from aura.core.request import AuraRequest
from starlette.responses import HTMLResponse

class PostListContext(TemplateContext):
    """Spec do que o template precisa — validado pelo Pydantic antes de renderizar."""
    posts: list[PostResponse]
    total: int
    page: int = 1

class PostsWebController:
    def __init__(self, service: PostService) -> None:
        self.service = service

    @html("/", template="posts/list.html")
    async def list_page(self) -> PostListContext:
        result = await self.service.list_posts()
        return PostListContext(posts=result.items, total=result.total)

    @html("/{post_id}")
    async def detail_page(
        self,
        post_id: int,
        request: AuraRequest,
    ) -> HTMLResponse:
        post = await self.service.get_post(post_id)
        ctx = PostDetailContext(post=post)
        # Fragmento htmx ou página completa dependendo do header
        if request.htmx.is_htmx:
            return await render("posts/partials/detail.html", ctx)
        return await render("posts/detail.html", ctx)

    @sse("/live")
    async def live_updates(self):
        """Server-Sent Events — yield dicts ou strings."""
        async for event in event_bus.subscribe("posts"):
            yield {"type": "new_post", "id": event.post_id}

@Module(
    providers=[PostService],
    controllers=[PostsController, PostsWebController],
    prefix="/posts",
)
class PostsModule:
    pass

# main.py — adiciona AuraTemplateModule para configurar Jinja2
app = Aura(
    modules=[
        AuraTemplateModule.for_root("templates"),
        PostsModule,
    ]
)
```

Templates têm acesso à função `url_for()` automaticamente:

```html
<!-- templates/posts/list.html -->
<a href="{{ url_for('posts_get_post', post_id=post.id) }}">Ver post</a>
```

### Diferença entre `@html` e `@get`

```python
class UserController:
    # JSON API
    @get("/")
    async def list_users_api(self) -> list[UserResponse]:
        return await self.service.list_users()          # → {"id": 1, "name": ...}

    # Página HTML renderizada no servidor
    @html("/", template="users/list.html")
    async def list_users_page(self) -> UserListContext:
        users = await self.service.list_users()
        return UserListContext(users=users)              # → renderiza users/list.html

    # Live updates via SSE
    @sse("/events")
    async def user_events(self):
        async for event in bus.subscribe("users"):
            yield {"action": event.type, "id": event.id}
```

---

## ⚙️ Middleware global

Middlewares factory-style (`CORSMiddleware(...)`, `CompressionMiddleware(...)`) e instâncias Starlette `Middleware(...)` funcionam em `Aura(middleware=[...])`:

```python
from aura import Aura
from aura.middleware import CORSMiddleware, RateLimitMiddleware, CompressionMiddleware
from aura.middleware import SessionMiddleware  # requer aura-web[session]
from starlette.middleware import Middleware

app = Aura(
    modules=[...],
    middleware=[
        CORSMiddleware(allow_origins=["https://app.example.com"], allow_methods=["*"]),
        CompressionMiddleware(minimum_size=512),
        Middleware(RateLimitMiddleware, max_requests=100, window_seconds=60),
        Middleware(SessionMiddleware, secret_key="..."),
    ],
)
```

---

## 📦 CLI completo

```bash
# Criar projeto
aura new meu-projeto                      # scaffolding completo e funcional
aura new meu-projeto --dir ~/projetos     # em outro diretório

# Generators (todos geram código funcional, sem stubs comentados)
aura generate module posts                # models + schemas + service + controller + module + tests
aura generate module posts --with-db      # idem + models.py e repository.py descomentados (AuraModel + Repository)
aura generate resource product            # alias para module
aura generate controller auth             # só o controller
aura generate service email               # @injectable service
aura generate schema invoice              # Create/Update/Response DTOs
aura generate guard jwt                   # Guard stub

# Flags dos generators
aura generate module posts --no-tests     # sem arquivo de testes
aura generate module posts --force        # sobrescrever existentes

# Servidor
aura run                                  # uvicorn (auto-detecta main:app)
aura run --reload                         # hot-reload em dev
aura run --host 0.0.0.0 --port 8080       # customizar host/porta
aura run --workers 4                      # múltiplos workers (produção)

# Banco de dados (Alembic por baixo, UX melhorada)
aura migrate init                         # cria alembic.ini + env.py
aura migrate make "add posts table"       # gera nova migration (timestamp se sem mensagem)
aura migrate up                           # aplica todas as migrations pendentes
aura migrate down                         # reverte a última
aura migrate status                       # lista estado atual
aura migrate stamp head                   # marca revisão sem rodar SQL
aura migrate reset                        # limpa banco + reaplica tudo (dev)

# Workers (jobs assíncronos)
aura worker                               # fila default, concurrency 4
aura worker --queue emails --queue push   # múltiplas filas (-q repetível)
aura worker --burst                       # processa fila e encerra (CI, one-shot)
aura worker --app main:app                # importa app para registrar @task
aura worker --broker-url redis://...      # SAQ com Redis em produção
aura worker --concurrency 8               # workers paralelos

# Shell interativo (Aura Tinker REPL)
aura tinker                               # inicia o shell interativo assíncrono (IPython)
aura tinker --repl bpython                # usa bpython se instalado
aura tinker --no-db                       # inicia sem conectar ao banco de dados
```

---

## 🔄 Jobs assíncronos

```python
from aura.jobs import task, periodic

@task(queue="emails")
async def send_welcome_email(user_id: int, email: str) -> None:
    # Executa em background; backend auto-selecionado pelo env var
    await mailer.send(email, "Bem-vindo!")

@periodic(cron="0 8 * * *")
async def daily_digest() -> None:
    # Roda todos os dias às 8h
    await newsletter.send_daily()

# Despachar em qualquer lugar:
await send_welcome_email.dispatch(user_id=42, email="user@example.com")
```

```bash
# Backend automático por env var:
# Sem AURA__JOBS__BROKER_URL → MemoryBackend (dev/test)
# Com AURA__JOBS__BROKER_URL=redis://... → SAQ com Redis

export AURA__JOBS__BROKER_URL=redis://localhost:6379
aura worker --app main:app -q emails -q default

# One-shot: drena jobs existentes e sai (útil em deploy/CI)
aura worker --burst --app main:app
```

### Database jobs — sem Redis (v1.5.0)

Para apps que já usam SQLAlchemy async, persista a fila de jobs no próprio banco — sem Redis nem SAQ:

```bash
# Requer pip install "aura-web[sqlalchemy]" e banco configurado
export AURA__DATABASE__URL=sqlite+aiosqlite:///./app.db
export AURA__JOBS__BACKEND=database

aura worker --app main:app
```

O `DatabaseBackend` grava jobs na tabela `aura_jobs`. O `AuraWorker` faz polling com claim atômico, retry e atualização de status. Ideal para deploys single-node ou quando Redis não está disponível.

Alternativa via `aura.toml`:

```toml
[database]
url = "postgresql+asyncpg://user:pass@localhost/mydb"

[jobs]
backend = "database"
```

---

## 📡 EventBus — pub/sub (v1.5.0)

Desacople domínios com eventos assíncronos. O EventBus é **opt-in** (`events.enabled=False` por padrão).

```python
from aura import Aura, Module, injectable
from aura.events import EventEnvelope, on_event

@on_event("user.created")
async def send_welcome_email(event: EventEnvelope) -> None:
    email = event.payload["email"]
    await mailer.send(email, "Bem-vindo!")

# Publicar de qualquer service:
from aura.events import get_event_bus

bus = get_event_bus()
await bus.publish("user.created", {"id": 1, "email": "user@example.com"})
```

Ative via env var ou `aura.toml`:

```bash
export AURA__EVENTS__ENABLED=true
export AURA__EVENTS__BACKEND=memory          # dev/test (padrão)
# export AURA__EVENTS__BACKEND=redis_streams  # produção multi-worker (requer [redis])
```

```toml
[events]
enabled = true
backend = "memory"           # memory | redis_streams | rabbitmq | kafka
redis_url = "redis://localhost:6379"
stream_prefix = "aura:events:"
```

Handlers em controllers/providers são descobertos automaticamente no startup (mesmo padrão de `@task` / `@get`). Ver [ADR-006](docs/decisions/ADR-006-event-bus.md).

---

## 🐰 Message brokers — RabbitMQ / Kafka (v1.5.0)

Backends enterprise para microserviços, com decorators estilo NestJS:

```python
from aura.events import EventPattern, MessagePattern, MessagingClient

class OrdersController:
    @EventPattern("order.placed")
    async def on_order_placed(self, payload: dict) -> None:
        await inventory.reserve(payload["items"])

    @MessagePattern("math.sum")
    async def sum_numbers(self, payload: dict) -> dict:
        return {"result": payload["a"] + payload["b"]}

# Cliente de mensagens:
client = MessagingClient(bus)
await client.emit("order.placed", {"order_id": 42})
result = await client.send("math.sum", {"a": 1, "b": 2})  # request/response
```

Configure o backend:

```bash
pip install "aura-web[rabbitmq]"   # aio-pika
# ou
pip install "aura-web[kafka]"      # aiokafka

export AURA__EVENTS__ENABLED=true
export AURA__EVENTS__BACKEND=rabbitmq
export AURA__EVENTS__RABBITMQ_URL=amqp://guest:guest@localhost/
```

| Backend | Uso | Extra |
|---------|-----|-------|
| `memory` | Dev, testes, single-process | — |
| `redis_streams` | Multi-process leve | `[redis]` |
| `rabbitmq` | AMQP, routing flexível, RPC | `[rabbitmq]` |
| `kafka` | Log distribuído, alto throughput | `[kafka]` |

`MessagingClient.send()` (request/response) funciona apenas em `rabbitmq` e `kafka`. Entrega **at-least-once** — handlers devem ser idempotentes. Ver [ADR-007](docs/decisions/ADR-007-message-brokers.md).

---

## 🔍 Logging & Debug Inteligente (AuraLogSystem v1.0)

> O logging tradicional do Python é síncrono e bloqueante por padrão, o que é péssimo para a performance de aplicações assíncronas.
> Aura resolve isso de forma elegante com o **AuraLogSystem v1.0**, um sistema de logs estruturado, assíncrono e altamente otimizado para o ciclo de vida de aplicações modernas.

### 🌟 Principais Recursos

- 🚀 **I/O Não-Bloqueante (Async-Safe)**: Integração nativa com `QueueHandler` e `QueueListener` da biblioteca padrão para delegar a escrita de logs em arquivo para uma thread em background. O Event Loop fica 100% livre e performático.
- 🧩 **Propagação de Contexto Automática**: Rastreamento automático de `request_id`, `user_id` e variáveis contextuais personalizadas em tarefas assíncronas e background jobs usando `contextvars`.
- 🛡️ **Sanitização de Dados Sensíveis**: Redação automática de senhas, tokens de API, cartões de crédito e outras informações confidenciais (`***REDACTED***`).
- 📁 **Daily Rotating File Handler**: Rotação diária e baseada em contagem de linhas automática, com detecção inteligente e avisos em ambientes multiprocesso.
- 💅 **Formatadores Flexíveis**: Suporte nativo a formato **Plain Text** (legível em desenvolvimento) e **JSON** estruturado (perfeito para Kibana, Grafana Loki, Datadog ou AWS CloudWatch).
- 🎛️ **Configuração Simplificada via `aura.toml` ou Env**: Níveis de log, rotações, filtros e destinos de forma declarativa.

---

### 💻 Como usar

#### 1. Usando a Facade `Log`

Você não precisa instanciar ou buscar loggers manualmente. Use a facade estática `Log` em qualquer lugar da sua aplicação:

```python
from aura.logging import Log

# Logs simples
Log.info("Serviço de pagamento inicializado")

# Logs estruturados com campos extras
Log.warning(
    "Tentativa de login malsucedida",
    username="jon_doe",
    ip_address="192.168.1.100"
)

# Registrando exceções com stack trace completo
try:
    1 / 0
except Exception as e:
    Log.error("Erro matemático", exc=e, operation="division")
```

#### 2. Propagação de Contexto (Contextvars)

O Aura gerencia e propaga contextos de log automaticamente. Se você rodar tarefas em segundo plano e quiser manter o mesmo `request_id` ou `user_id` nos logs da tarefa:

```python
from aura.logging import run_with_context, Log
import asyncio

async def background_task(user_id: int):
    # O contexto contendo o request_id e user_id estará disponível aqui!
    Log.info("Processando relatórios para o usuário em background", user_id=user_id)

# Em seu controller ou service:
async def handle_request():
    context = {"request_id": "req-9872134", "user_id": 42}

    # Executa a coroutine propagando o contexto
    await run_with_context(background_task(42), context)
```

#### 3. Interceptor de Requisições HTTP

Para que todas as requisições HTTP tenham um `request_id` único e gerem logs automáticos de acesso, basta usar o `RequestLogInterceptor` como middleware ASGI em seu `main.py`:

```python
from starlette.middleware import Middleware
from aura import Aura
from aura.logging import RequestLogInterceptor

app = Aura(
    modules=[...],
    middleware=[
        Middleware(
            RequestLogInterceptor,
            log_headers=True,             # DEBUG: headers com redação automática (v1.4.x)
            generate_request_id=True,     # Gera UUID quando X-Request-ID não for enviado
            extract_request_id_header="x-request-id",
        ),
    ],
)
```

Com `log_headers=True`, campos sensíveis (`authorization`, `cookie`, `x-api-key`, etc.) são substituídos por `***REDACTED***` antes de ir para o log — o mesmo `Sanitizer` usado nos formatadores estruturados.

#### 4. Sanitização Automática

Campos confidenciais são limpos dos seus logs estruturados antes de serem exibidos ou gravados:

```python
# O dicionário extra contendo dados sensíveis será sanitizado automaticamente!
Log.info("Requisição recebida", payload={
    "username": "admin",
    "password": "senhaSuperSecreta123",  # -> Reduzido para ***REDACTED***
    "token": "bearer xyz123"             # -> Reduzido para ***REDACTED***
})
```

#### 5. Configuração

Personalize o comportamento do sistema de logs no seu arquivo de configurações `aura.toml` ou via variáveis de ambiente com o prefixo `AURA__LOGGING__` ou `LOG_`:

```toml
[logging]
level = "INFO"                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
format = "plain"                # plain ou json
console = true                  # Exibe logs no console/stdout
file = true                     # Grava logs em arquivo
dir = "storage/logs"            # Diretório de gravação
max_lines = 10000               # Limite de linhas por arquivo para rotação
sanitize_fields = ["password", "token", "cvv", "api_key", "authorization"]
```

---

## 📊 Perfilamento de Consultas & Observabilidade de Banco de Dados

O Aura possui ferramentas nativas integradas ao core para auditar, mensurar e otimizar todas as queries SQL executadas contra o banco de dados, auxiliando a detectar problemas clássicos como consultas N+1 de forma automática.

### 🌟 Principais Recursos

- ⏱️ **QueryCountMiddleware**: Middleware ASGI global que intercepta requisições HTTP, contabiliza queries e calcula o tempo total de latência, retornando automaticamente os headers de resposta em desenvolvimento:
  - `X-Query-Count`: Número de queries executadas no request.
  - `X-Query-Time-Ms`: Latência acumulada das consultas em milissegundos.
  - `X-Query-N1-Risk`: Avisos sobre detecções de queries redundantes ou N+1.
- 🎯 **@track_queries**: Decorador assíncrono para funções de serviço ou controllers que monitora e emite warnings automáticos sobre queries lentas, contagens acima do limite ou duplicações SQL.
- 🔄 **Auto-conversão de ORM e DTOs (Zero Boilerplate)**: O roteador do Aura inspeciona automaticamente as assinaturas de tipo de retorno das funções dos seus controladores (ex: `list[UserResponse]`). Quando ativado, ele valida e converte objetos SQLAlchemy ou listas de modelos de banco de dados diretamente em DTOs Pydantic nativos, eliminando a necessidade de mapeamentos manuais e tratando tipos complexos (como `datetime`, `Decimal` e `UUID`) automaticamente.

---

### 💻 Como usar

#### 1. Ativando o Middleware Global
Adicione o `QueryCountMiddleware` ao inicializar seu app para que todas as rotas passem a incluir headers de observabilidade automaticamente em modo debug:

```python
from aura import Aura, QueryCountMiddleware
from starlette.middleware import Middleware
from modules.users.module import UsersModule

app = Aura(
    modules=[UsersModule],
    middleware=[
        Middleware(QueryCountMiddleware),
    ],
)
```

#### 2. Decorador `@track_queries`
Monitore uma função assíncrona específica emitindo alertas se ela passar de um limite pré-determinado de queries:

```python
from aura import track_queries

@track_queries(threshold=5)
async def list_users(self):
    # Roda as queries SQL do banco de dados
    # Se o total de queries passar de 5, emite um warning de performance no terminal!
    return await self.user_repository.list()
```

---

## ⛓️ Interceptadores (Interceptors)

> Os **Interceptadores** são uma funcionalidade extremamente poderosa do Aura inspirada no ecossistema NestJS. Eles envolvem a execução de rotas e manipuladores (handlers), permitindo que você execute lógica personalizada **antes** e **depois** do processamento de cada requisição no nível do controller.

Diferente dos middlewares tradicionais do ASGI (que rodam no nível da requisição bruta HTTP), os interceptadores rodam no ciclo de vida de resolução de rotas do framework, fornecendo acesso direto a contextos de execução assíncronos.

Registre interceptors globais via `Aura(interceptors=[...])` — aplicados a JSON, HTML, SSE e WebSocket:

```python
from aura import Aura
from aura.interceptors import TimingInterceptor, RequestLogInterceptor

app = Aura(
    modules=[PostsModule],
    interceptors=[TimingInterceptor(), RequestLogInterceptor()],
)
```

### 🌟 O que eles podem fazer?

- ⏱️ **Métricas de Performance**: Medir tempo exato de processamento de controladores.
- 📝 **Logs de Acesso**: Gerar auditorias estruturadas de requisições.
- 📦 **Transformação de Respostas**: Envolver ou mutar o retorno de um endpoint.
- 💾 **Caching**: Interceptar a requisição e retornar um valor cacheado antes do handler rodar.

---

### 📦 Interceptadores Prontos

O Aura já vem com dois interceptadores prontos para uso em `aura.interceptors`:

#### 1. `TimingInterceptor`

Adiciona automaticamente o cabeçalho `X-Process-Time` (com precisão de microssegundos) na resposta de qualquer rota interceptada.

```python
from aura.interceptors import TimingInterceptor

# Pode ser chamado e encadeado em pipelines de roteamento
```

#### 2. `RequestLogInterceptor` (ou `LoggingInterceptor`)

Grava logs de acesso estruturados a nível de rota no logger `aura.access`. Ele captura: método, URL de acesso, status da resposta, e tempo decorrido em milissegundos (`elapsed_ms`), integrando de forma limpa as variáveis de contexto (`request_id`, `user_id`, etc.).

---

### 🛠️ Criando e Usando Interceptadores Personalizados

Para construir seu próprio interceptador, herde da classe abstrata `Interceptor` de `aura.interceptors` e implemente o método `intercept(self, request, handler, call_next)`:

```python
import time
from typing import Any
from aura.interceptors import Interceptor

class SimpleAuditInterceptor(Interceptor):
    async def intercept(self, request: Any, handler: Any, call_next: Any) -> Any:
        # 1. Executa lógica ANTES do handler rodar
        print(f"Auditoria: Rota {request.url.path} foi chamada!")

        # 2. Chama o próximo passo (próximo interceptador ou o handler em si)
        start_time = time.perf_counter()
        response = await call_next(request)

        # 3. Executa lógica DEPOIS do handler rodar
        duration = time.perf_counter() - start_time
        print(f"Auditoria: Rota respondeu com status {response.status_code} em {duration:.4f}s")

        return response
```

Para usar o interceptador em sua rota, basta chamá-lo encadeando o protocolo de execução no pipeline desejado:

```python
interceptor = SimpleAuditInterceptor()
response = await interceptor.intercept(request, handler, call_next)
```

---

## 🌌 Shell Interativo — Aura Tinker (REPL)

> Escreva código assíncrono e execute queries no banco sem importar nada manualmente.
> O `aura tinker` localiza e carrega todos os Models, Repositories, Services e Schemas do projeto em menos de 1 segundo.

O Aura Tinker inicializa um ambiente REPL interativo inteligente pré-carregado com os recursos da sua aplicação.

### 🌟 Principais Recursos:
- 🔍 **Auto-Discovery**: Varredura automática recursiva que detecta e importa todos os componentes do seu projeto (Models, Services, Repositories e Schemas) no namespace global.
- ⚡ **Top-Level Await**: Suporte nativo a comandos assíncronos diretos (com `await`) utilizando IPython.
- 🔄 **Injeção de Dependências**: Inicialização automática do container de DI (`container`) e do banco de dados (`db`) no escopo do shell.
- 🛠️ **Helper `sync(...)`**: Execução simples de funções assíncronas em shells de fallback (`bpython` e `python` padrão).

```bash
# Inicializa o REPL (IPython por padrão)
aura tinker

# Abre o shell sem conectar ao banco de dados
aura tinker --no-db

# Especifica o shell de backend
aura tinker --repl bpython
```

### 🗄️ Gerenciamento de Sessão no Shell:
- **Opção 1 (Padrão Recomendado):** Usando o gerenciador de contexto `async with db.session() as session:` (gerencia commits e fechamentos de forma automática e segura).
- **Opção 2 (Testes Rápidos no REPL):** Usando a factory direta `session = db._session_factory()` (ideal para escrever comandos em linha única sem recuo/indentação no terminal, exigindo chamar `await session.commit()` e `await session.close()` de forma manual ao final).

Confira a [Documentação Detalhada do Aura Tinker](docs/tinker.md) para ver exemplos práticos e entender a arquitetura de auto-discovery do shell.

---

## ✅ O que já está pronto

### Core

- [x] App ASGI (Starlette core)
- [x] Routing: `@get`, `@post`, `@put`, `@delete`, `@patch`, `@ws`
- [x] Parameter binding: `Body`, `Query`, `Param`, `Header`, `Cookie`
- [x] Injeção automática de `AuraRequest` por type hint (sem marcador)
- [x] `@Module` com `providers`, `controllers`, `imports`, `exports`, `prefix`, `tags`, `guards`
- [x] `DIContainer` com lifetimes SINGLETON, SCOPED, TRANSIENT
- [x] Scoped container por request HTTP/WS e transações implícitas via ContextVar (sem boilerplate manual)
- [x] `@injectable` (com e sem parênteses)
- [x] `inject()` — `Annotated[T, inject()]` para injeção explícita por type hint
- [x] `Schema` e `ResponseSchema` (Pydantic v2)
- [x] Hierarquia completa de `HTTPException` (400–504)
- [x] `Guard` interface com `can_activate` / `on_denied`
- [x] `AuraConfig` com `pydantic-settings` e `aura.toml`
- [x] `AuraRequest` com `.htmx`, `.user`, `.container`
- [x] Response helpers: `ok()`, `created()`, `no_content()`, `redirect()`

### ORM

- [x] `AuraModel` com `id`, `created_at`, `updated_at`
- [x] `Repository[T]`: `get`, `get_or_raise`, `list`, `create`, `update`, `delete`, `exists`, `count`, `first`
- [x] `Repository[T]`: `bulk_create`, `bulk_update`, `bulk_delete`
- [x] `Repository[T].paginate()` — retorna `Page[T]` com `items`, `total`, `page`, `per_page`, `has_next`
- [x] `async with db.session()` — transação com commit/rollback automático
- [x] `async with db.transaction()` — unit-of-work para múltiplos repositórios
- [x] `DatabaseManager` — auto-init via `AURA__DATABASE__URL` na startup do app
- [x] `AuraModel.__abstract__ = True` — suporte a modelos abstratos intermediários
- [x] SQLAlchemy 2.x async
- [x] Sistema de Database Seeders com suporte a DI, idempotência e proteção de Produção
- [x] `Model Factories` & `SubFactory` integrados ao `Faker` com suporte a `ContextVar` de transações

### Auth & Segurança

- [x] `JWTGuard` — valida `Authorization: Bearer`, popula `request.state.user` (requer `aura-web[jwt]` / PyJWT)
- [x] `RateLimitGuard` — sliding window, LRU, headers `X-RateLimit-*` em 429
- [x] `SessionMiddleware` — sessões assinadas em cookie (requer `aura-web[session]`)
- [x] `RateLimitMiddleware` — rate limit global por IP (backend memória ou Redis, headers `X-RateLimit-*`)
- [x] `CORSMiddleware`
- [x] `CompressionMiddleware`

### Jobs

- [x] `@task` e `@periodic` decorators
- [x] `MemoryBackend` (dev/test — sem dependências externas)
- [x] `DatabaseBackend` — fila persistente em SQL, sem Redis (`AURA__JOBS__BACKEND=database`)
- [x] `SAQBackend` — Redis via SAQ (`Queue.from_url`, timeout/scheduled em segundos)
- [x] Backend auto-detectado por `AURA__JOBS__BACKEND` / `AURA__JOBS__BROKER_URL`
- [x] `aura worker` funcional com SAQ native worker, database polling e TaskRegistry

### Events & Messaging (v1.5.0)

- [x] `EventBus` + `EventEnvelope` — contrato pub/sub com metadados uniformes
- [x] `InMemoryEventBus` e `RedisStreamsEventBus` (requer `[redis]`)
- [x] `@on_event("topic")` + `EventHandlerRegistry` com wiring no startup
- [x] `EventsConfig` opt-in (`events.enabled=False` por padrão)
- [x] `RabbitMQEventBus` e `KafkaEventBus` (extras `[rabbitmq]` / `[kafka]`)
- [x] `@EventPattern` / `@MessagePattern` — handlers estilo NestJS microservices
- [x] `MessagingClient` — `emit()` fire-and-forget e `send()` request/response

### Templates (HTML server-rendered)

- [x] `TemplateContext` — Pydantic model como spec do template
- [x] `HtmlResponse` com suporte a headers HX-\*
- [x] `AuraTemplateEngine` — Jinja2 com async nativo
- [x] `Component` — classes Python com `Props` tipadas
- [x] `HtmxInfo` — detecta requests htmx via headers
- [x] `HtmxResponseHeaders` — builder fluente para HX-Trigger, HX-Redirect, etc.
- [x] `render()`, `render_string()`, `render_to_string()`
- [x] `@html` decorator — rotas que retornam HTML (integrado ao router)
- [x] `@sse` decorator — Server-Sent Events (streaming async)
- [x] Auto-conversão: `TemplateContext` → render, `str` → HtmlResponse, `Response` → passthrough
- [x] HTML error pages para exceções HTTP em rotas `@html`
- [x] `AuraTemplateModule.for_root()` — configura Jinja2 via módulo, `on_startup` chamado automaticamente
- [x] `url_for(name, **params)` global em todos os templates

### OpenAPI / Docs

- [x] OpenAPI 3.1 auto-gerado
- [x] `securitySchemes` — `JWTGuard` expõe `BearerAuth`; merge de `Router.tags`
- [x] Swagger UI embutido em `/docs`
- [x] ReDoc embutido em `/redoc`
- [x] `/health` automático

### CLI

- [x] `aura version`
- [x] `aura new <name>` — scaffolding completo com módulo Users funcional
- [x] `aura generate module/resource/controller/service/schema/guard`
- [x] `aura generate module --with-db` — descomenta models.py e repository.py com código real
- [x] `aura run` (uvicorn/granian)
- [x] `aura migrate init/make/up/down/stamp/status/reset` — Alembic com UX melhorada (spinners, cores)
- [x] `aura worker` — SAQ nativo; `--queue`, `--burst`, `--app` funcionais em produção
- [x] `aura tinker` — shell REPL interativo com auto-discovery assíncrono e top-level await

### Observabilidade & Logging (AuraLogSystem v1.0)

- [x] **Facade `Log`** — métodos estáticos convenientes (`Log.info()`, `Log.debug()`, etc.) com merging automático de contexto.
- [x] **I/O Não-Bloqueante** — fila de logs (`QueueHandler` e `QueueListener` nativos) para evitar travar o event loop assíncrono.
- [x] **Propagação de Contexto** — suporte automático via `contextvars` para manter `request_id`, `user_id` e dados customizados correlacionados.
- [x] **Sanitização de Dados Sensíveis** — redação automática (ex: senhas, tokens de API, cartões) configurável.
- [x] **Daily Rotating File Handler** — rotação diária de logs, thread-safe, com aviso de segurança multiprocesso integrado.
- [x] **Formatadores Plain & JSON** — formato texto legível em dev, JSON estruturado ideal para datadog/loki em produção.
- [x] **RequestLogInterceptor** — interceptor/middleware ASGI para extrair/gerar `request_id`; redação de headers sensíveis com `log_headers=True`
- [x] **Propagador em background** — `run_with_context` para propagar dados de log em background tasks/jobs.
- [x] **Suíte de Testes Robusta** — cobertura abrangente de toda a infraestrutura de observabilidade com 39 testes dedicados.

### Qualidade

- [x] 713 testes passando
- [x] mypy strict (0 erros em `aura/`)
- [x] ruff (0 warnings)
- [x] GitHub Actions CI (Python 3.10 + 3.12)
- [x] Publicado no PyPI como `aura-web`

---

## 🚧 O que está pendente

### Routing — DX (v0.3.0)

- [x] **Inferência automática de `Param()`** — `async def get_user(self, user_id: int)` inferido de forma inteligente a partir do path template `/{user_id}` (sem precisar de `Annotated[int, Param()]`)
- [x] **Serialização de alta performance com `TypeAdapter`** — `@get("/", response=Page[PostResponse])` compila e valida as respostas em nível de rota usando Pydantic v2 a velocidades nativas (C/Rust)
- [x] **Auto-conversão de ORM e DTOs** — Serialização transparente de objetos/listas de ORM para schemas de resposta DTO sem loops de validação lentos em Python

### DI Container (v0.3.0)

- [x] **Scoped container por request HTTP/WS** — resolvido com sucesso! Injeção automática de `AsyncSession` e propagação dinâmica via `current_session` ContextVar.

### Interceptors (v0.3.0)

- [x] **Interface `Interceptor`** — pipeline `intercept(request, handler, call_next)` + `Aura(interceptors=[...])` (v1.4.0)
- [x] **`LoggingInterceptor`** — log de método, path, status e duração em cada request (implementado como `RequestLogInterceptor` em v0.3.1)

### Roadmap futuro (v0.4.0+)

- [ ] `@Gateway` WebSocket — rooms, broadcast, `on_connect`/`on_disconnect`
- [ ] `AdminModule` — painel admin auto-gerado a partir dos models
- [ ] GraphQL via Strawberry (`GraphQLModule.for_root`)
- [ ] `aura generate resource <name> --crud --db`
- [ ] Multi-tenancy (row-level e schema-level)
- [ ] OpenTelemetry integration — traces/metrics automáticos
- [x] Structured logging (AuraLogSystem v1.0 concluído)
- [ ] Site de documentação (MkDocs + GitHub Pages)
- [ ] Exemplos completos: `examples/todo-app`, `examples/blog`
- [ ] Benchmarks vs FastAPI / Django / Litestar

---

## ⚠️ Limitações conhecidas

| Limitação                                                  | Impacto                        | Workaround                               |
| ---------------------------------------------------------- | ------------------------------ | ---------------------------------------- |
| `static()` em templates retorna `/static/{path}` hardcoded | Baixo                          | Usar Starlette `StaticFiles` diretamente |
| `QuerySet.delete()` sem filtros exige `allow_unfiltered=True` | Médio — breaking v1.2.x | Usar `.filter()` ou opt-in explícito |
| `component(...)` em templates exige `await` (v1.3.x) | Médio — breaking | `{{ await component(...) }}` — [ADR-002](docs/decisions/ADR-002-async-templates-only.md) |
| `redirect()` rejeita URLs absolutas | Baixo | Usar `RedirectResponse` para externos |
| `RateLimitGuard` sem headers em 200 (só em 429) | Baixo | Usar `RateLimitMiddleware` global se precisar de `Remaining` em toda resposta |
| Mensagens de erro HTTP em inglês; docs em português | Baixo | Customizar `message=` em guards/exceptions |
| `aura run --reload` reinicia o processo inteiro            | Baixo em dev                   | Comportamento normal do uvicorn          |


---

## 🗂️ Extras instaláveis

```bash
pip install "aura-web[uvicorn]"      # servidor ASGI (recomendado)
pip install "aura-web[granian]"      # servidor Rust (mais rápido)
pip install "aura-web[templates]"    # Jinja2 + HTML rendering
pip install "aura-web[sqlalchemy]"   # ORM async + migrations (Alembic)
pip install "aura-web[saq]"          # async job queue (Redis via SAQ)
pip install "aura-web[redis]"        # Redis client async
pip install "aura-web[rabbitmq]"     # EventBus RabbitMQ (aio-pika)
pip install "aura-web[kafka]"        # EventBus Kafka (aiokafka)
pip install "aura-web[jwt]"          # JWT auth (PyJWT[crypto])
pip install "aura-web[session]"      # sessões em cookie (itsdangerous)
pip install "aura-web[all]"          # tudo acima
```

---

## 📄 Licença

MIT © Jonathas David

---

<p align="center">
  <a href="https://pypi.org/project/aura-web/">PyPI</a> ·
  <a href="docs/">Documentação</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="https://github.com/jonathasdavidd/Aura/issues">Issues</a>
</p>

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
    <img src="https://img.shields.io/badge/version-0.2.0-blue?style=flat-square" />
    <img src="https://img.shields.io/badge/tests-243%20passing-brightgreen?style=flat-square" />
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

| Problema real | Como outros resolvem | Como Aura resolve |
|---|---|---|
| `settings.py` com 500 linhas | Django: um arquivo global | `aura.toml` modular + config type-safe por seção |
| ORM síncrono em stack async | Django: `sync_to_async()` em todo lugar | SQLAlchemy 2.x async genuíno desde o core |
| Serializers fazem tudo (DRF) | ViewSet + Serializer + Permissions misturados | Schemas (DTOs) separados de Services e Controllers |
| Celery complexo, sem async | Celery 5: ainda sem `async def` nativo | `@task(queue="emails")` — async de verdade |
| DI só funciona no HTTP | FastAPI: `Depends()` não roda em jobs/CLI | `DIContainer` funciona em qualquer contexto |
| Typing quebra com mypy | Django: metaclass magic quebra o type checker | Pydantic v2 em todo o framework, mypy strict |
| Sem estrutura de projeto | FastAPI: 82+ boilerplates diferentes | `@Module` NestJS-inspired com DI encapsulado |
| N+1 queries em produção | DRF: serializers aninhados sem select_related | `Repository[T]` com métodos otimizados |
| Context dict não tipado | Django templates: `render(request, "tmpl.html", {"key": val})` | `TemplateContext` (Pydantic) — validado antes de renderizar |
| Auth manual em cada projeto | FastAPI: `Depends(get_current_user)` por conta própria | `JWTGuard` + `RateLimitGuard` + `SessionMiddleware` built-in |

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
from aura.orm import AuraModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, Boolean

class Post(AuraModel):
    __tablename__ = "posts"

    title:     Mapped[str]  = mapped_column(String(200))
    body:      Mapped[str]  = mapped_column(Text)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
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
        stmt = (
            select(Post)
            .where(Post.published == True)
            .order_by(Post.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
```

```python
# modules/posts/service.py
from aura import injectable, NotFoundException
from aura.orm import db, Page
from .models import Post
from .repository import PostRepository
from .schemas import CreatePostDTO, UpdatePostDTO, PostResponse

@injectable
class PostService:
    async def list_posts(self, page: int = 1) -> Page[PostResponse]:
        async with db.session() as session:
            result = await PostRepository(session).paginate(
                page=page, per_page=20, order_by="created_at"
            )
            return Page(
                items=[PostResponse.model_validate(p) for p in result.items],
                total=result.total,
                page=result.page,
                per_page=result.per_page,
                has_next=result.has_next,
            )

    async def get_post(self, post_id: int) -> PostResponse:
        async with db.session() as session:
            post = await PostRepository(session).get_or_raise(post_id)
            return PostResponse.model_validate(post)

    async def create_post(self, data: CreatePostDTO) -> PostResponse:
        async with db.session() as session:
            post = await PostRepository(session).create(**data.model_dump())
            return PostResponse.model_validate(post)

    async def transfer_posts(self, from_id: int, to_id: int) -> None:
        """Múltiplos repos na mesma transação."""
        async with db.transaction() as session:
            repo = PostRepository(session)
            await repo.update(from_id, published=False)
            await repo.update(to_id, published=True)
            # rollback automático se qualquer linha lançar exceção
```

```python
# modules/posts/controller.py
from typing import Annotated
from aura import get, post, put, delete, Body, Param
from aura.orm import Page
from .schemas import CreatePostDTO, UpdatePostDTO, PostResponse
from .service import PostService

class PostsController:
    def __init__(self, service: PostService) -> None:
        self.service = service

    @get("/")
    async def list_posts(self, page: Annotated[int, Query()] = 1) -> Page[PostResponse]:
        return await self.service.list_posts(page)

    @get("/{post_id}")
    async def get_post(self, post_id: Annotated[int, Param()]) -> PostResponse:
        return await self.service.get_post(post_id)

    @post("/", status=201)
    async def create_post(self, body: Annotated[CreatePostDTO, Body()]) -> PostResponse:
        return await self.service.create_post(body)

    @put("/{post_id}")
    async def update_post(
        self,
        post_id: Annotated[int, Param()],
        body:    Annotated[UpdatePostDTO, Body()],
    ) -> PostResponse:
        return await self.service.update_post(post_id, body)

    @delete("/{post_id}", status=204)
    async def delete_post(self, post_id: Annotated[int, Param()]) -> None:
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

---

## 🔐 Auth, Guards e Segurança

### JWTGuard — autenticação Bearer

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
)
```

### RateLimitGuard — proteção por rota

```python
from aura import post, Module
from aura.guards import RateLimitGuard

class AuthController:
    @post("/login", guards=[RateLimitGuard(max_requests=5, window=60)])
    async def login(self, body: Annotated[LoginDTO, Body()]) -> TokenResponse:
        # Máximo 5 tentativas por minuto por IP
        ...
```

### SessionMiddleware — sessões em cookie

```python
from aura import Aura
from aura.middleware import SessionMiddleware  # pip install "aura-web[session]"

app = Aura(
    modules=[...],
    middleware=[
        SessionMiddleware(secret_key="chave-secreta-longa"),
    ],
)

# Em qualquer controller:
class CartController:
    @post("/add")
    async def add_item(self, request: AuraRequest, body: Annotated[ItemDTO, Body()]) -> dict:
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
        post_id: Annotated[int, Param()],
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

```python
from aura import Aura
from aura.middleware import CORSMiddleware, RateLimitMiddleware, CompressionMiddleware
from aura.middleware import SessionMiddleware  # requer aura-web[session]

app = Aura(
    modules=[...],
    middleware=[
        CORSMiddleware,
        RateLimitMiddleware,       # rate limit global (por IP)
        CompressionMiddleware,
        SessionMiddleware(secret_key="..."),
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
aura worker                               # processa todas as filas (MemoryBackend em dev)
aura worker --queue emails --queue push   # filas específicas
aura worker --broker-url redis://...      # SAQ com Redis em produção
aura worker --concurrency 8              # workers paralelos
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
aura worker
```

---

## ✅ O que já está pronto

### Core
- [x] App ASGI (Starlette core)
- [x] Routing: `@get`, `@post`, `@put`, `@delete`, `@patch`, `@ws`
- [x] Parameter binding: `Body`, `Query`, `Param`, `Header`, `Cookie`
- [x] Injeção automática de `AuraRequest` por type hint (sem marcador)
- [x] `@Module` com `providers`, `controllers`, `imports`, `exports`, `prefix`, `tags`, `guards`
- [x] `DIContainer` com lifetimes SINGLETON, SCOPED, TRANSIENT
- [x] `@injectable` (com e sem parênteses)
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

### Auth & Segurança
- [x] `JWTGuard` — valida `Authorization: Bearer`, popula `request.state.user` (requer `aura-web[jwt]`)
- [x] `RateLimitGuard` — rate limit por rota (sliding window, só stdlib)
- [x] `SessionMiddleware` — sessões assinadas em cookie (requer `aura-web[session]`)
- [x] `RateLimitMiddleware` — rate limit global por IP
- [x] `CORSMiddleware`
- [x] `CompressionMiddleware`

### Jobs
- [x] `@task` e `@periodic` decorators
- [x] `MemoryBackend` (dev/test — sem dependências externas)
- [x] `SAQBackend` — Redis via SAQ (requer `aura-web[saq]`)
- [x] Backend auto-detectado por `AURA__JOBS__BROKER_URL`
- [x] `aura worker` funcional com SAQ native worker e TaskRegistry

### Templates (HTML server-rendered)
- [x] `TemplateContext` — Pydantic model como spec do template
- [x] `HtmlResponse` com suporte a headers HX-*
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
- [x] `aura worker` — SAQ nativo em produção, MemoryBackend em dev

### Qualidade
- [x] 243 testes passando
- [x] mypy strict (0 erros em 77 arquivos)
- [x] ruff (0 warnings)
- [x] GitHub Actions CI (Python 3.10 + 3.12)
- [x] Publicado no PyPI como `aura-web`

---

## 🚧 O que está pendente

### Routing — DX (v0.3.0)

- [ ] **Inferência automática de `Param()`** — `async def get_user(self, user_id: int)` deveria inferir `Param()` quando `user_id` aparece no path `/{user_id}`, sem precisar de `Annotated[int, Param()]`
- [ ] **`response_model` para serialização estrita** — `@get("/", response=UserResponse)` garante que apenas campos do schema são retornados

### DI Container (v0.3.0)

- [ ] **Scoped container por request HTTP** — middleware que cria scope e injeta `AsyncSession` automaticamente via `request.state.container`; habilita `def __init__(self, session: AsyncSession)` sem `async with db.session()` manual

### Interceptors (v0.3.0)

- [ ] **Interface `Interceptor`** — `before(context) / after(context, response)` pipeline
- [ ] **`LoggingInterceptor`** — log de método, path, status e duração em cada request

### Roadmap futuro (v0.4.0+)

- [ ] `@Gateway` WebSocket — rooms, broadcast, `on_connect`/`on_disconnect`
- [ ] `AdminModule` — painel admin auto-gerado a partir dos models
- [ ] GraphQL via Strawberry (`GraphQLModule.for_root`)
- [ ] `aura generate resource <name> --crud --db`
- [ ] Multi-tenancy (row-level e schema-level)
- [ ] OpenTelemetry integration — traces/metrics automáticos
- [ ] Structured logging com `structlog`
- [ ] Site de documentação (MkDocs + GitHub Pages)
- [ ] Exemplos completos: `examples/todo-app`, `examples/blog`
- [ ] Benchmarks vs FastAPI / Django / Litestar

---

## ⚠️ Limitações conhecidas

| Limitação | Impacto | Workaround |
|---|---|---|
| Path params sem `Annotated[T, Param()]` não são resolvidos | Médio — mais verboso que ideal | Sempre usar `Annotated[int, Param()]` |
| `static()` em templates retorna `/static/{path}` hardcoded | Baixo | Usar Starlette `StaticFiles` diretamente |
| `aura run --reload` reinicia o processo inteiro | Baixo em dev | Comportamento normal do uvicorn |

---

## 🗂️ Extras instaláveis

```bash
pip install "aura-web[uvicorn]"      # servidor ASGI (recomendado)
pip install "aura-web[granian]"      # servidor Rust (mais rápido)
pip install "aura-web[templates]"    # Jinja2 + HTML rendering
pip install "aura-web[sqlalchemy]"   # ORM async + migrations (Alembic)
pip install "aura-web[saq]"          # async job queue (Redis via SAQ)
pip install "aura-web[redis]"        # Redis client async
pip install "aura-web[jwt]"          # JWT auth (python-jose)
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
  <a href="https://github.com/jonathasdavidd/Aura/issues">Issues</a>
</p>

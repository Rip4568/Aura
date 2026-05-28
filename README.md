<p align="center">
  <h1 align="center">🌌 Aura Framework</h1>
  <p align="center">
    <strong>O framework Python moderno que você sempre quis.</strong><br/>
    Async nativo · Type-safe · Spec-Driven · Módulos · Jobs integrados · HTML server-rendered
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python" />
    <img src="https://img.shields.io/badge/pydantic-v2-orange?style=flat-square" />
    <img src="https://img.shields.io/badge/pypi-aura--web-purple?style=flat-square" />
    <img src="https://img.shields.io/badge/async-first-green?style=flat-square" />
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

---

## 🚀 Instalação

```bash
# Instalação básica (API REST)
pip install "aura-web[uvicorn]"

# Com suporte a templates HTML (Jinja2)
pip install "aura-web[uvicorn,templates]"

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

### API REST com ORM assíncrono

> Django tem ORM mas é síncrono — precisa de `sync_to_async()` em todo lugar.  
> FastAPI não tem ORM — você conecta SQLAlchemy na mão com `Depends(get_db)`.  
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
# modules/posts/schemas.py  ← a Spec (SDD): fonte da verdade para validação e OpenAPI
from aura import Schema

class CreatePostDTO(Schema):
    title: str
    body: str

class UpdatePostDTO(Schema):
    title: str | None = None
    body:  str | None = None

class PostResponse(Schema):
    model_config = {"from_attributes": True}  # aceita ORM objects diretamente

    id:        int
    title:     str
    body:      str
    published: bool
```

```python
# modules/posts/repository.py
from aura.orm import Repository
from sqlalchemy import select
from .models import Post

class PostRepository(Repository[Post]):
    model = Post

    # Repository[T] já inclui: get, get_or_raise, list, create, update,
    # delete, exists, count, first, bulk_create — sem escrever SQL.
    # Adicione métodos customizados para consultas específicas:

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
from aura.orm import db          # singleton DatabaseManager — inicializado no main.py
from .models import Post
from .repository import PostRepository
from .schemas import CreatePostDTO, UpdatePostDTO, PostResponse

@injectable
class PostService:
    """Business logic — não sabe nada de HTTP, só de Posts."""

    async def list_posts(self) -> list[PostResponse]:
        async with db.session() as session:           # ← abre transação async
            posts = await PostRepository(session).list()
            return [PostResponse.model_validate(p) for p in posts]

    async def get_post(self, post_id: int) -> PostResponse:
        async with db.session() as session:
            post = await PostRepository(session).get_or_raise(post_id)
            return PostResponse.model_validate(post)  # 404 automático se não existir

    async def create_post(self, data: CreatePostDTO) -> PostResponse:
        async with db.session() as session:           # ← commit automático ao sair
            post = await PostRepository(session).create(**data.model_dump())
            return PostResponse.model_validate(post)

    async def update_post(self, post_id: int, data: UpdatePostDTO) -> PostResponse:
        async with db.session() as session:
            updates = {k: v for k, v in data.model_dump().items() if v is not None}
            post = await PostRepository(session).update(post_id, **updates)
            return PostResponse.model_validate(post)  # rollback automático em exceção

    async def delete_post(self, post_id: int) -> None:
        async with db.session() as session:
            deleted = await PostRepository(session).delete(post_id)
            if not deleted:
                raise NotFoundException(f"Post {post_id} not found")
```

```python
# modules/posts/controller.py  ← handlers finos: recebem input, chamam service, retornam
from typing import Annotated
from aura import get, post, put, delete, Body, Param
from .schemas import CreatePostDTO, UpdatePostDTO, PostResponse
from .service import PostService

class PostsController:
    def __init__(self, service: PostService) -> None:
        self.service = service          # injetado pelo DI container

    @get("/")
    async def list_posts(self) -> list[PostResponse]:
        return await self.service.list_posts()

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
from aura import Aura
from modules.posts.module import PostsModule

# Opção 1: deixar o Aura inicializar automaticamente via env var
# export AURA__DATABASE__URL=sqlite+aiosqlite:///./app.db
app = Aura(modules=[PostsModule], title="Blog API", version="1.0.0")

# Opção 2: inicializar manualmente (legado / mais controle)
# from aura.orm import db
# db.init("sqlite+aiosqlite:///./app.db")
# Para criar as tabelas em dev (use `aura migrate up` em produção):
# import asyncio; asyncio.run(db.create_all(Post))
```

```bash
aura run --reload
# POST /posts/    → cria post (persiste no banco)
# GET  /posts/    → lista todos
# GET  /posts/1   → busca por ID (404 automático se não existir)
# PUT  /posts/1   → atualiza
# DELETE /posts/1 → remove
# GET  /docs      → Swagger UI auto-gerado
```

### Full-stack com HTML (Jinja2 + htmx)

> `@html` e `@sse` são separados de `@get`/`@post` — eles coexistem no mesmo controller.
> Use `@get`/`@post`/etc. para JSON API. Use `@html` para páginas server-rendered.

```python
from aura import Module
from aura.templates import html, sse, render, TemplateContext, AuraTemplateModule

class PostListContext(TemplateContext):
    """Spec do que o template posts/list.html precisa — validado pelo Pydantic."""
    posts: list[PostResponse]
    total: int
    page: int = 1

class PostsWebController:
    def __init__(self, service: PostService) -> None:
        self.service = service

    @html("/", template="posts/list.html")
    async def list_page(self) -> PostListContext:
        """Retorna TemplateContext → router renderiza automaticamente."""
        posts = await self.service.list_posts()
        return PostListContext(posts=posts, total=len(posts))

    @html("/{post_id}")
    async def detail_page(
        self,
        post_id: Annotated[int, Param()],
        request: AuraRequest,
    ) -> HtmlResponse:
        """Controle total: retorna fragmento htmx ou página completa."""
        post = await self.service.get_post(post_id)
        ctx = PostDetailContext(post=post)
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

# main.py — adiciona AuraTemplateModule
app = Aura(
    modules=[
        AuraTemplateModule.for_root("templates"),  # configura o engine Jinja2
        PostsModule,
    ]
)
```

### Diferença entre `@html` e `@get`

```python
class UserController:
    # ✅ JSON API — use @get, @post, @put, @delete
    @get("/")
    async def list_users_api(self) -> list[UserResponse]:
        return await self.service.list_users()          # → {"id": 1, "name": ...}

    # ✅ Página HTML — use @html
    @html("/", template="users/list.html")
    async def list_users_page(self) -> UserListContext:
        users = await self.service.list_users()
        return UserListContext(users=users)              # → renderiza users/list.html

    # ✅ Live updates — use @sse
    @sse("/events")
    async def user_events(self):
        async for event in bus.subscribe("users"):
            yield {"action": event.type, "id": event.id}  # → text/event-stream
```

---

## 📦 CLI completo

```bash
# Criar projeto
aura new meu-projeto                     # scaffolding completo e funcional
aura new meu-projeto --dir ~/projetos    # em outro diretório

# Generators (todos geram código funcional, sem comentários)
aura generate module posts               # schemas + service + controller + module + tests
aura generate resource product           # alias para module
aura generate controller auth            # só o controller
aura generate service email              # @injectable service
aura generate schema invoice             # Create/Update/Response DTOs
aura generate guard jwt                  # Guard stub

# Flags
aura generate module posts --no-tests    # sem arquivo de testes
aura generate module posts --force       # sobrescrever existentes

# Servidor
aura run                                 # uvicorn (auto-detecta main:app)
aura run --reload                        # hot-reload em dev
aura run --host 0.0.0.0 --port 8080      # customizar host/porta
aura run --workers 4                     # múltiplos workers (produção)

# Banco de dados
aura migrate make "add posts table"      # criar migration (Alembic)
aura migrate up                          # aplicar migrations
aura migrate down                        # reverter última
aura migrate status                      # listar status

# Workers (jobs assíncronos)
aura worker --queue emails               # processar fila específica
```

---

## 🏗️ Estrutura de um módulo

```
modules/
└── posts/
    ├── __init__.py
    ├── schemas.py       ← DTOs: CreatePostDTO, UpdatePostDTO, PostResponse
    ├── service.py       ← @injectable PostService (business logic)
    ├── controller.py    ← HTTP handlers (@get, @post, @html, @sse)
    ├── module.py        ← @Module(providers, controllers, prefix, tags)
    └── repository.py    ← Repository[Post] (quando usar SQLAlchemy)
```

---

## 📚 Documentação

| Documento | Descrição |
|---|---|
| [Motivação e Comparativo](docs/motivation.md) | Por que Aura existe, dores que resolve |
| [Schemas e Validação](docs/schemas-validation.md) | DTOs, Pydantic v2, validação |
| [ORM e Queries](docs/orm-queries.md) | Repository pattern, CRUD, filtros |
| [Jobs e Workers](docs/jobs-workers.md) | `@task`, queues, periodic jobs |
| [Módulos e DI](docs/modules-di.md) | Sistema de módulos, injeção de dependência |
| [Templates](docs/templates.md) | `@html`, `@sse`, `TemplateContext`, Components, htmx |
| [SDD](docs/sdd.md) | Spec-Driven Development — a filosofia do Aura |
| [Roadmap](docs/roadmap.md) | O que está sendo construído |

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

### ORM
- [x] `AuraModel` com `id`, `created_at`, `updated_at`
- [x] `Repository[T]`: `get`, `list`, `create`, `update`, `delete`, `exists`, `count`, `bulk_create`
- [x] Suporte a SQLAlchemy 2.x async

### Jobs
- [x] `@task` e `@periodic` decorators
- [x] `MemoryBackend` (dev/test)
- [x] SAQ backend stub (integração pendente)

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
- [x] `AuraTemplateModule.for_root()` — configura Jinja2 via módulo

### OpenAPI / Docs
- [x] OpenAPI 3.1 auto-gerado
- [x] Swagger UI embutido em `/docs`
- [x] ReDoc embutido em `/redoc`
- [x] `/health` automático

### CLI
- [x] `aura version`
- [x] `aura new <name>` — scaffolding completo com módulo Users funcional
- [x] `aura generate module/resource/controller/service/schema/guard`
- [x] `aura run` (uvicorn/granian)
- [x] `aura migrate make/up/down/status` (stubs)
- [x] `aura worker` (stub)

### Qualidade
- [x] 156 testes passando
- [x] Publicado no PyPI como `aura-web`

---

## 🚧 O que está pendente

### Alta prioridade (v0.2.0)

- [ ] **`AuraTemplateModule` no ciclo de vida** — `on_startup` precisa ser chamado pelo `ModuleRegistry` para configurar o engine antes dos primeiros requests
- [ ] **`url_for()` em templates** — resolver URLs por nome de rota dentro do Jinja2
- [ ] **`static()` tag real** — integrar com `StaticFiles` do Starlette
- [ ] **`DatabaseManager` na startup** — ler `AURA__DATABASE__URL` e iniciar pool automaticamente
- [ ] **`aura migrate make/up/down`** — implementar os wrappers Alembic (stubs existem)
- [ ] **SAQ backend integrado** — `AuraTask.dispatch()` usando Redis + SAQ em produção
- [ ] **`aura worker` funcional** — conectar ao SAQ e processar filas

### Média prioridade (v0.3.0)

- [ ] **`JWTGuard` builtin** — `python-jose`, extrai `Bearer`, popula `request.state.user`
- [ ] **`RateLimitGuard`** — rate limiting por IP/usuário
- [ ] **`Repository.paginate()`** — retorna `Page[T]` com `total`, `has_next`, etc.
- [ ] **`async with db.transaction()`** — unit-of-work para múltiplos repos
- [ ] **Interceptors** — `LoggingInterceptor`, `TimingInterceptor`, `CacheInterceptor`
- [ ] **`@Gateway` WebSocket** — rooms, broadcast, `on_connect`/`on_disconnect`
- [ ] **Islands Architecture** — `[data-island]` + `/js/islands.js` para hidratação seletiva
- [ ] **`CORSMiddleware` simplificado** — config via `AuraConfig.cors`

### Roadmap futuro (v0.4.0+)

- [ ] `AdminModule` — painel admin auto-gerado a partir dos models
- [ ] GraphQL via Strawberry (`GraphQLModule.for_root`)
- [ ] Multi-tenancy (row-level e schema-level)
- [ ] Plugin system (`RedisPlugin`, `S3Plugin`, `SentryPlugin`)
- [ ] Benchmarks vs FastAPI / Django / Litestar
- [ ] Site de documentação (MkDocs + GitHub Pages)
- [ ] Exemplos completos: `examples/todo-app`, `examples/blog`, `examples/ecommerce`

---

## ⚠️ O que precisa melhorar

### Bugs conhecidos / limitações atuais

| Item | Status | Impacto |
|---|---|---|
| `AuraTemplateModule.on_startup` não é chamado pelo registry | Workaround: chamar `set_engine()` manualmente | Alto — templates não funcionam sem setup manual |
| `aura migrate make` não implementado | Stub retorna "não implementado" | Alto — devs precisam usar Alembic diretamente |
| `aura worker` não processa filas | Stub sem SAQ integrado | Alto — jobs ficam no MemoryBackend |
| SAQ backend não conecta em produção | `saq_backend.py` existe mas não está integrado | Alto — jobs morrem ao reiniciar o servidor |
| Erro em route `@html` sem `template=` com `TemplateContext` | Lança `ValueError` claro | Baixo — erro descritivo |
| `_resolve_params` não resolve parâmetros de path sem `Annotated[int, Param()]` | Precisa do marker explícito | Médio — mais verboso que ideal |

### Melhorias de DX (Developer Experience)

- **`@get` sem `Annotated`** — `async def get_user(self, user_id: int)` deveria inferir `Param()` para path params
- **Mensagens de erro melhores** — quando DI falha, o stack trace atual é confuso
- **Hot-reload de módulos** — hoje `aura run --reload` reinicia o processo inteiro; modules poderiam ser recarregados individualmente
- **Autocompletar CLI** — `aura generate <TAB>` não funciona em todos os shells
- **`aura generate component <name>`** — gera Component class + template HTML juntos

### Performance

- Serialização com `msgspec` (10x mais rápido que Pydantic para respostas simples)
- Route caching — compilação de rotas acontece a cada startup
- Template bytecode cache para produção

---

## 🗂️ Extras instaláveis

```bash
pip install "aura-web[uvicorn]"      # servidor ASGI (recomendado)
pip install "aura-web[granian]"      # servidor Rust (mais rápido)
pip install "aura-web[templates]"    # Jinja2 + HTML rendering
pip install "aura-web[sqlalchemy]"   # ORM async + migrations
pip install "aura-web[saq]"          # async job queue
pip install "aura-web[redis]"        # Redis client async
pip install "aura-web[jwt]"          # JWT auth (python-jose)
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

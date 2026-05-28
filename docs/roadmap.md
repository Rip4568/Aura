# Roadmap — O que já foi construído e o que está por vir

## Estado Atual: Alpha (v0.2.0)

O Aura está funcional e testado para uso em produção em projetos internos. O core está estável.

---

## ✅ Construído (v0.1.0 → v0.2.0)

### Core
- [x] **ASGI app** — baseado em Starlette, 100% compatível com qualquer servidor ASGI
- [x] **Routing** — `@get`, `@post`, `@put`, `@delete`, `@patch`, `@ws`
- [x] **Parameter binding** — `Body[T]`, `Query[T]`, `Param[T]`, `Header[T]`, `Cookie[T]` via `Annotated`
- [x] **Type coercion automática** — `int`, `float`, `bool` extraídos de strings de query/path
- [x] **Resposta automática** — dict/list/Pydantic model → JSONResponse transparente
- [x] **WebSocket** — suporte básico via `@ws`

### Módulos & DI
- [x] **Sistema de módulos** — `@Module(providers, controllers, imports, exports, prefix, tags, guards)`
- [x] **DIContainer** — resolve por tipo, suporta `SINGLETON`, `SCOPED`, `TRANSIENT`
- [x] **`@injectable`** — funciona com e sem parênteses
- [x] **Auto-resolução** — `__init__` type hints resolvidos automaticamente
- [x] **Scoped containers** — `container.create_scope()` para isolamento por request

### Schemas & Validação
- [x] **`Schema(BaseModel)`** — base com `from_attributes=True`, strip whitespace
- [x] **`ResponseSchema`** — distinção semântica para respostas
- [x] **Pydantic v2** — validação em Rust, 50x mais rápida que v1
- [x] **422 automático** — erros de validação retornam JSON estruturado
- [x] **OpenAPI 3.1** — gerado automaticamente dos type hints e decorators

### ORM
- [x] **`AuraModel`** — `id`, `created_at`, `updated_at` automáticos; `__abstract__ = True`
  com `_AuraRegistry(DeclarativeBase)` interno; suporta modelos abstratos intermediários
- [x] **`Repository[T]`** — `get`, `get_or_raise`, `list`, `create`, `update`, `delete`
- [x] **Métodos extras** — `exists`, `count`, `first`, `bulk_create`, `bulk_update`, `bulk_delete`
- [x] **SQLAlchemy 2.x async** — async real (não thread-pool)
- [x] **`DatabaseManager`** — singleton com `init()`, `session()`, `close()`
- [x] **`from aura import AuraModel`** — import direto do pacote principal (opcional, não quebra sem SQLAlchemy)

### Exceções HTTP
- [x] **Hierarquia completa** — 400, 401, 403, 404, 405, 409, 422, 429, 500, 503, 504
- [x] **Respostas estruturadas** — `{"error": {"status": 404, "code": "NOT_FOUND", "message": "..."}}`
- [x] **Headers customizados** — `UnauthorizedException(headers={"WWW-Authenticate": "Bearer"})`

### Guards
- [x] **Interface `Guard`** — `can_activate(request) -> bool`, `on_denied(request)`
- [x] **Guards por rota** — `@get("/path", guards=[AuthGuard])`
- [x] **Guards por módulo** — `@Module(guards=[JWTGuard])`
- [x] **Guards globais** — `Aura(guards=[RateLimitGuard])`

### Jobs & Workers
- [x] **`@task`** — `queue`, `retry`, `timeout`, `priority`
- [x] **`@periodic`** — `cron`, `run_on_startup`
- [x] **`MemoryBackend`** — para desenvolvimento e testes
- [x] **`TaskRegistry`** — registro global de tasks
- [x] **Dispatch assíncrono** — `await my_task.dispatch(**kwargs)`

### Config
- [x] **`AuraConfig(BaseSettings)`** — lê de `.env`, env vars, TOML
- [x] **Nested config** — `AURA__DATABASE__URL`, `AURA__SERVER__PORT`
- [x] **Subconfigs** — `ServerConfig`, `DatabaseConfig`, `JobsConfig`

### CLI
- [x] **`aura version`** — versão atual
- [x] **`aura run`** — inicia servidor
- [x] **`aura worker`** — inicia worker de background jobs
- [x] **`aura new`** — scaffolding de novo projeto
- [x] **`aura generate`** — módulo, controller, service, schema, guard
  (inclui `models.py` + `repositories.py` comentados mostrando padrão correto)
- [x] **`aura migrate`** — wrapper do Alembic (stub — comandos `make`/`up`/`down` pendentes)

### Developer Experience
- [x] **`/health`** — liveness probe automático em toda app
- [x] **`/openapi.json`** — spec OpenAPI 3.1
- [x] **`/docs`** — Swagger UI embutido
- [x] **`/redoc`** — Redoc embutido
- [x] **Suporte a Uvicorn e Granian** — `app.run(server="granian")`
- [x] **Testes** — 156 testes, cobrindo todos os subsistemas
- [x] **mypy strict** — 0 erros em 74 arquivos
- [x] **GitHub Actions CI** — matrix Python 3.10/3.12, typecheck, lint
- [x] **Makefile** — `make test`, `make typecheck`, `make lint`, `make check`

---

## 🚧 Em Desenvolvimento (v0.2.0 → v0.3.0)

### Migrations (bloqueante para prod)
- [ ] **`aura migrate make "<msg>"`** — wrapper Alembic para criar migration
- [ ] **`aura migrate up` / `aura migrate down`** — aplicar e reverter

### ORM Melhorias
- [ ] `Repository.paginate()` com metadados (`total`, `page`, `has_next`, `items`)
- [ ] `async with db.transaction()` — unit-of-work para múltiplos repositories
- [ ] `DatabaseManager` inicializado automaticamente na startup do app

### Guards & Auth
- [ ] **`JWTGuard`** builtin — plug-and-play com `python-jose`
- [ ] **`RateLimitGuard`** — rate limiting por IP/usuário
- [ ] **`SessionMiddleware`** — sessões assinadas

### SAQ Backend (produção)
- [ ] Integração real com SAQ + Redis
- [ ] Worker CLI conectando ao SAQ
- [ ] Backend auto-seleção: `AURA__JOBS__BROKER_URL` presente → SAQ, ausente → MemoryBackend

---

## 📋 Planejado (v0.3.0+)

### Interceptors
Pipeline de antes/depois do handler (logging, caching, transformação):

```python
class LoggingInterceptor(Interceptor):
    async def intercept(self, context: ExecutionContext, next: Handler) -> Response:
        start = time.time()
        response = await next(context)
        duration = time.time() - start
        logger.info(f"{context.method} {context.path} → {response.status_code} ({duration:.3f}s)")
        return response

app = Aura(interceptors=[LoggingInterceptor])
```

### WebSocket Gateway
API de alto nível para WebSockets com rooms e broadcast:

```python
from aura.gateway import Gateway, Subscribe, MessageBody

@Gateway("/chat")
class ChatGateway:
    @Subscribe("message")
    async def handle_message(
        self,
        body: Annotated[MessageDTO, MessageBody()],
        client: WebSocketClient,
    ) -> None:
        await client.room("general").broadcast(body)
    
    async def on_connect(self, client: WebSocketClient) -> None:
        await client.join("general")
    
    async def on_disconnect(self, client: WebSocketClient) -> None:
        await client.leave("general")
```

### Pipes (Transformação de Dados)
Transformações encadeadas aplicadas aos parâmetros antes do handler:

```python
class ParseIntPipe(Pipe):
    def transform(self, value: str) -> int:
        return int(value)

class ValidationPipe(Pipe):
    def transform(self, value: dict, schema: type[Schema]) -> Schema:
        return schema.model_validate(value)

@get("/users/{id}")
async def get_user(id: Annotated[str, Param(), ParseIntPipe]) -> UserResponse:
    ...
```

### GraphQL
Integração opcional com Strawberry:

```python
import strawberry
from aura.graphql import GraphQLModule

@strawberry.type
class Query:
    @strawberry.field
    async def users(self) -> list[UserType]:
        ...

@Module(
    imports=[GraphQLModule.forRoot(Query)],
    ...
)
class AppModule:
    pass
```

### gRPC
Suporte a serviços gRPC alongside HTTP:

```python
from aura.grpc import GrpcController, grpc_method

@GrpcController("UserService")
class UserGrpcController:
    @grpc_method
    async def GetUser(self, request: GetUserRequest) -> GetUserResponse:
        ...
```

### Multi-tenancy
Isolamento de dados por tenant:

```python
@Module(
    strategy=TenantStrategy.SCHEMA,  # ou ROW_LEVEL, DATABASE
    tenant_resolver=HeaderTenantResolver("X-Tenant-Id"),
)
class AppModule:
    pass
```

### Admin Panel
Interface administrativa auto-gerada:

```python
from aura.admin import AdminModule, AdminResource

@AdminResource(model=User, list_display=["name", "email", "active"])
class UserAdmin:
    pass

@Module(
    imports=[AdminModule.forRoot([UserAdmin])],
    ...
)
class AppModule:
    pass
```

### CLI — Code Generation
```bash
aura generate module orders
# Cria: orders/module.py, controller.py, service.py, repository.py, schemas.py

aura generate resource user --crud
# Cria model + migration + repository + service + controller + schemas + testes

aura generate guard jwt
# Cria: guards/jwt.guard.py com estrutura base
```

### Plugin System
```python
from aura.plugins import AuraPlugin

class RedisPlugin(AuraPlugin):
    async def on_startup(self, app: Aura) -> None:
        self.redis = await aioredis.create_pool(app.config.redis_url)
        app.container.register_instance(Redis, self.redis)
    
    async def on_shutdown(self, app: Aura) -> None:
        self.redis.close()
        await self.redis.wait_closed()

app = Aura(plugins=[RedisPlugin()])
```

---

## 🔬 Pesquisa / Experimental

| Feature | Descrição | Status |
|---|---|---|
| `msgspec` integration | Serialização 10x mais rápida que Pydantic | Avaliando |
| HTTP/3 | Via Hypercorn + QUIC | Aguardando ecosystem |
| Rust extensions | Hot paths em Rust via PyO3 | Experimental |
| AI code gen | Gerar controllers/services a partir do schema | PoC |
| Edge deployment | Suporte a Cloudflare Workers via Python WASM | Futuro distante |

---

## Versioning

| Versão | Status | Foco |
|---|---|---|
| `0.1.0` | ✅ Released | Core estável, routing, DI, ORM, jobs básico |
| `0.2.0` | ✅ Released | bulk ops, scaffold models/repos, AuraModel abstract, mypy 0 erros, CI |
| `0.3.0` | 🚧 Em dev | Migrations, `paginate()`, JWTGuard, SAQ backend, Interceptors |
| `0.4.0` | 📋 Planejado | WebSocket Gateway, Pipes, GraphQL, gRPC |
| `1.0.0` | 🎯 Meta | API estável, prod-ready, documentação completa |

---

## Como Contribuir

```bash
git clone https://github.com/seu-usuario/Aura
cd Aura
uv pip install -e ".[dev]"

# Rodar testes
pytest

# Com cobertura
pytest --cov=aura --cov-report=html

# Lint
ruff check aura/
mypy aura/
```

Áreas prioritárias para contribuição:
1. **SAQ backend** — integração com Redis + worker loop
2. **Documentação** — exemplos de projetos reais
3. **Benchmarks** — comparação com FastAPI, Django, Litestar
4. **Interceptors** — implementação do pipeline
5. **CLI scaffolding** — geração de código mais completa

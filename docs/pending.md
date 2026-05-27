# Pendências — Tudo que falta construir e melhorar

> Lista completa e atualizada de itens pendentes no Aura Framework.
> Organizado por prioridade e área.

---

## 🔴 Alta Prioridade (próxima release v0.2.0)

### Templates — sistema criado, precisa de integração

- [ ] **Router: suporte a `response_type="html"`** — o `_wrap_http_handler` no `router.py` precisa
  detectar quando o handler retorna `HtmlResponse` ou `TemplateContext` e fazer o render
  automaticamente (sem o dev precisar chamar `await render()` manualmente)
- [ ] **`@html` decorator integrado com roteamento** — atualmente o decorator existe mas o
  router não o distingue de `@get` para fazer o render automático
- [ ] **`AuraTemplateModule.on_startup`** — integrar corretamente com o ciclo de vida do `ModuleRegistry`
  (atualmente o `on_startup` do módulo não é chamado pelo registry)
- [ ] **`@sse` decorator** — implementar o wrapper ASGI para Server-Sent Events no router
- [ ] **Jinja2 como dependência principal** — mover de `[templates]` extra para dependência base
  (templates são essenciais para full-stack apps)
- [ ] **`static()` tag com resolução real** — integrar com `StaticFiles` do Starlette
- [ ] **`url_for()` tag** — resolver URLs de rotas por nome no template
- [ ] **Middleware de auto-reload de templates** — usar `watchfiles` para detectar mudanças em dev

### ORM & Database

- [ ] **`aura migrate make "<msg>"`** — wrapper do Alembic para criar migrations
  (`aura/cli/commands/migrate.py` existe mas `make` não está implementado)
- [ ] **`aura migrate up` / `aura migrate down`** — aplicar e reverter migrations
- [ ] **`DatabaseManager` no ciclo de vida do app** — hoje o dev precisa chamar `db.init()` manualmente;
  deveria acontecer na startup quando `AURA__DATABASE__URL` estiver configurado
- [ ] **`async with db.transaction()`** — unit-of-work explícito para múltiplos repositórios
- [ ] **`Repository.paginate()`** — método com retorno `Page[T]` contendo `total_pages`, `has_next`, etc.

### Jobs & Workers

- [ ] **SAQ Backend real** — `aura/jobs/backends/saq_backend.py` existe mas não está integrado
  com o `AuraTask.dispatch()`; hoje só o `MemoryBackend` funciona
- [ ] **`aura worker` CLI** — o comando existe mas não conecta ao SAQ nem processa tasks
- [ ] **Backend auto-seleção** — detectar `AURA__JOBS__BROKER_URL` na startup e configurar
  automaticamente SAQ ou MemoryBackend

---

## 🟡 Média Prioridade (v0.3.0)

### Guards & Auth

- [ ] **`JWTGuard` builtin** — guard plug-and-play com `python-jose`, extrai `Authorization: Bearer`
  e popula `request.state.user`
- [ ] **`RateLimitGuard`** — rate limiting por IP/usuário usando Redis ou in-memory
- [ ] **`SessionMiddleware`** — sessões assinadas (cookie seguro com `itsdangerous`)
- [ ] **`CORSMiddleware` simplificado** — wrapper do Starlette `CORSMiddleware` com config
  via `AuraConfig.cors`

### Interceptors

- [ ] **Interface `Interceptor`** — `before(context) / after(context, response)` pipeline
- [ ] **`LoggingInterceptor`** — log de método, path, status, duração
- [ ] **`TimingInterceptor`** — header `X-Response-Time` em ms
- [ ] **`CacheInterceptor`** — cache de resposta via Redis ou in-memory
- [ ] **Integração com roteamento** — `@get("/path", interceptors=[LoggingInterceptor])`

### Templates — features avançadas

- [ ] **Islands Architecture** — `IslandProps` + script `/js/islands.js` que hidrata
  `[data-island]` com React/Vue/Svelte seletivamente
- [ ] **Macros/helpers builtin** — `{{ pagination(ctx) }}`, `{{ flash_messages() }}`, 
  `{{ csrf_token() }}`
- [ ] **Email templates** — `render_to_string()` + integração com SMTP/SendGrid
- [ ] **PDF generation** — `render_to_pdf()` via WeasyPrint ou Playwright
- [ ] **Template linter** — validar em build time que todos os `{{ var }}` existem no TemplateContext

### WebSocket Gateway

- [ ] **`@Gateway` decorator** — classe com `@Subscribe("event")` para WebSocket
- [ ] **Rooms/channels** — `client.join("room")`, `client.room("room").broadcast(msg)`
- [ ] **`on_connect` / `on_disconnect` hooks**
- [ ] **Integração com DI** — services injetáveis no Gateway

---

## 🟢 Baixa Prioridade / Roadmap Futuro (v0.4.0+)

### CLI — Code Generation

- [ ] **`aura generate module <name>`** — cria `module.py`, `controller.py`, `service.py`,
  `repository.py`, `schemas.py` com boilerplate correto
- [ ] **`aura generate resource <name> --crud`** — model + migration + CRUD completo
- [ ] **`aura generate component <name>`** — component class + template HTML
- [ ] **`aura generate guard <name>`** — guard com estrutura base
- [ ] **`aura new <project-name>`** — scaffolding completo de novo projeto com estrutura Aura

### GraphQL (opcional)

- [ ] **`GraphQLModule.for_root(schema)`** — integração com Strawberry
- [ ] **`/graphql` endpoint** com playground
- [ ] **Subscriptions** via WebSocket

### gRPC (opcional)

- [ ] **`@GrpcController`** — controller que responde gRPC ao lado de HTTP
- [ ] **Code generation** a partir de `.proto`

### Multi-tenancy

- [ ] **`TenantStrategy.ROW_LEVEL`** — coluna `tenant_id` em todas as tabelas
- [ ] **`TenantStrategy.SCHEMA`** — schema PostgreSQL por tenant
- [ ] **`TenantResolver`** — extrair tenant de header, subdomínio, JWT

### Admin Panel

- [ ] **`AdminModule`** — interface administrativa auto-gerada a partir dos models
- [ ] **`@AdminResource`** — `list_display`, `search_fields`, `filters`
- [ ] **CRUD automático** — create/edit/delete a partir do schema

### Plugin System

- [ ] **`AuraPlugin` interface** — `on_startup`, `on_shutdown`, acesso ao container
- [ ] **`RedisPlugin`** — connection pool automático
- [ ] **`S3Plugin`** — client AWS S3 configurado
- [ ] **`SentryPlugin`** — error tracking automático

---

## 🔧 Melhorias Técnicas

### Performance

- [ ] **`msgspec` como serialização alternativa** — 10x mais rápido que Pydantic para
  request/response simples (manter Pydantic para validação)
- [ ] **Route caching** — cache de rotas compiladas para evitar recompilação a cada request
- [ ] **Template bytecode cache** — Jinja2 `bytecode_cache` para produção

### DI Container

- [ ] **Circular dependency detection** — erro claro ao invés de `RecursionError`
- [ ] **Lazy providers** — instanciar apenas quando primeiro solicitado
- [ ] **Scoped container por request HTTP** — middleware que cria scope e injeta no request

### Testing

- [ ] **`AuraTestCase`** — base class com helpers para testes de integração
- [ ] **`mock_service()`** — substituir service no DI container em testes
- [ ] **`snapshot_testing()`** — assert de HTML renderizado contra snapshot

### Observabilidade

- [ ] **`X-Query-Count` header** — contar queries SQL por request em debug
- [ ] **N+1 detector middleware** — logar aviso quando > 10 queries no mesmo request
- [ ] **OpenTelemetry integration** — traces/metrics automáticos
- [ ] **Structured logging** — `structlog` ou `python-json-logger` integrado

### Docs & DX

- [ ] **`docs/` website** — deploy em GitHub Pages com MkDocs
- [ ] **Exemplos completos** — `examples/todo-app`, `examples/blog`, `examples/ecommerce`
- [ ] **Benchmarks** — comparação com FastAPI, Django, Litestar
- [ ] **VSCode Extension** — snippets e goto-definition para decorators Aura

---

## 📦 PyPI & Distribuição

- [ ] **Revogar token PyPI exposto** — gerar novo token em https://pypi.org/manage/account/token/
- [ ] **CI/CD com GitHub Actions** — rodar testes + build + publish automático em tags
- [ ] **Badges dinâmicos no README** — coverage, PyPI version, downloads
- [ ] **Changelog** — `CHANGELOG.md` seguindo Keep a Changelog
- [ ] **v0.1.1 com fixes** — corrigir integração `@html` + router antes de divulgar

---

## ✅ Concluído (referência)

- [x] Core ASGI app (Starlette)
- [x] Routing: `@get`, `@post`, `@put`, `@delete`, `@patch`, `@ws`
- [x] Parameter binding: `Body`, `Query`, `Param`, `Header`, `Cookie`
- [x] `@Module` system com imports/exports
- [x] `DIContainer` com SINGLETON, SCOPED, TRANSIENT
- [x] `@injectable` decorator (com e sem parênteses)
- [x] `Schema` e `ResponseSchema` (Pydantic v2)
- [x] `Repository[T]`: `get`, `list`, `create`, `update`, `delete`, `exists`, `count`, `bulk_create`
- [x] `AuraModel` com `id`, `created_at`, `updated_at`
- [x] Hierarquia completa de `HTTPException` (400-504)
- [x] `Guard` interface
- [x] `@task` e `@periodic` decorators
- [x] `MemoryBackend` para jobs em dev/test
- [x] `AuraConfig` com `pydantic-settings`
- [x] CLI: `version`, `run`, `worker`, `new`, `generate`, `migrate`
- [x] OpenAPI 3.1 auto-gerado
- [x] Swagger UI + Redoc embutidos
- [x] `/health` automático
- [x] 138 testes passando
- [x] **Templates**: `TemplateContext`, `HtmlResponse`, `AuraTemplateEngine`, `Component`, `HtmxInfo`, `render()`, `@html`, `@sse`
- [x] `AuraRequest.htmx` — detecta requests htmx
- [x] Publicado no PyPI como `aura-web`
- [x] Docs: motivation, schemas, ORM, jobs, modules, SDD, templates, roadmap

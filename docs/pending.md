# Pendências — Tudo que falta construir e melhorar

> Lista completa e atualizada de itens pendentes no Aura Framework.  
> Atualizado em 2026-05-27. Organizado por prioridade e área.

---

## ✅ Recentemente concluído

- [x] **`@html` integrado ao router** — `_wrap_html_handler` detecta `response_type="html"`,
  converte `TemplateContext` → render, `str` → `HtmlResponse`, `Response` → passthrough
- [x] **`@sse` integrado ao router** — `_wrap_sse_handler` converte async generator em
  `StreamingResponse(text/event-stream)` com serialização JSON automática
- [x] **`AuraRequest` injeção por tipo** — `_resolve_params` injeta `AuraRequest` (e
  `starlette.Request`) automaticamente quando o parâmetro é tipado como tal, sem `Annotated`
- [x] **HTML error pages** — exceções HTTP em rotas `@html` retornam página HTML (não JSON)
- [x] **`aura new <name>`** — scaffolding completo e funcional (15 arquivos, módulo Users real,
  7 testes de integração, conftest com `ASGITransport`)
- [x] **`aura generate module/resource/controller/service/schema/guard`** — 6 subcomandos
  gerando código funcional (sem stubs comentados)
- [x] **`aura generate resource --no-tests`** — flag `--tests/--no-tests` adicionada ao `resource`

---

## 🔴 Alta Prioridade (v0.2.0)

### Templates — integração com ciclo de vida

- [ ] **`AuraTemplateModule.on_startup` integrado com `ModuleRegistry`** — hoje o dev
  precisa chamar `set_engine()` manualmente; o `ModuleRegistry.collect_routes()` ou o
  `Aura._build()` precisa chamar `on_startup(container, debug)` de todos os módulos registrados
- [ ] **`url_for()` global no Jinja2** — registrar `url_for(name, **params)` como global
  no engine, resolvendo a URL de uma rota pelo nome do handler
- [ ] **`static()` tag com `StaticFiles` real** — hoje retorna `/static/{path}` hardcoded;
  precisa resolver a URL real via `request.url_for("static", path=...)`
- [ ] **Middleware de auto-reload de templates** — usar `watchfiles` para detectar mudanças
  nos arquivos `.html` em dev sem reiniciar o processo

### ORM & Database

- [ ] **`aura migrate make "<msg>"`** — implementar o wrapper Alembic para criar migrations
  (o stub em `aura/cli/commands/migrate.py` existe mas lança NotImplementedError)
- [ ] **`aura migrate up` / `aura migrate down`** — aplicar e reverter migrations
- [ ] **`DatabaseManager` no ciclo de vida do app** — ler `AURA__DATABASE__URL` na startup
  e iniciar o pool SQLAlchemy automaticamente (hoje o dev chama `db.init()` manualmente)
- [ ] **`Repository.paginate()`** — método com retorno `Page[T]` com `total`, `page`,
  `has_next`, `items`
- [ ] **`async with db.transaction()`** — unit-of-work para operações em múltiplos repositories

### Jobs & Workers

- [ ] **SAQ backend integrado** — `aura/jobs/backends/saq_backend.py` existe mas `AuraTask.dispatch()`
  só usa `MemoryBackend`; precisa detectar `AURA__JOBS__BROKER_URL` e usar SAQ automaticamente
- [ ] **`aura worker` funcional** — conectar ao SAQ e processar filas configuradas
- [ ] **Backend auto-seleção** — se `AURA__JOBS__BROKER_URL` estiver definido, usar SAQ;
  caso contrário, usar `MemoryBackend` silenciosamente

---

## 🟡 Média Prioridade (v0.3.0)

### Guards & Auth

- [ ] **`JWTGuard` builtin** — extrai `Authorization: Bearer`, valida com `python-jose`,
  popula `request.state.user` com payload tipado
- [ ] **`RateLimitGuard`** — rate limiting por IP/usuário via Redis ou in-memory sliding window
- [ ] **`SessionMiddleware`** — sessões assinadas via cookie seguro com `itsdangerous`
- [ ] **`CORSMiddleware` simplificado** — wrapper do Starlette com config via `AuraConfig.cors`

### Routing — DX improvements

- [ ] **Inferência automática de `Param()` para path params** — `async def get_user(self, user_id: int)`
  deveria deduzir `Param()` quando `user_id` aparece no path `/{user_id}`, sem precisar de
  `Annotated[int, Param()]`
- [ ] **`response_model` para serialização estrita** — `@get("/", response=UserResponse)` deveria
  garantir que apenas campos do schema são retornados (como FastAPI faz)

### Interceptors

- [ ] **Interface `Interceptor`** — `before(context) / after(context, response)` pipeline
- [ ] **`LoggingInterceptor`** — log de método, path, status e duração em cada request
- [ ] **`TimingInterceptor`** — adiciona header `X-Response-Time` com duração em ms
- [ ] **`CacheInterceptor`** — cache de resposta com TTL via Redis ou in-memory
- [ ] **Integração com routing** — `@get("/", interceptors=[LoggingInterceptor()])`

### Templates — features avançadas

- [ ] **Islands Architecture** — `IslandProps` + `/js/islands.js` que hidrata elementos
  `[data-island]` seletivamente com React/Vue/Svelte sem recarregar a página
- [ ] **Macros builtin** — `{{ pagination(ctx) }}`, `{{ flash_messages() }}`, `{{ csrf_token() }}`
- [ ] **Email templates** — `render_to_string()` funciona; falta integração com SMTP/SendGrid
- [ ] **PDF generation** — `render_to_pdf()` via WeasyPrint ou Playwright
- [ ] **Template linter** — validar em build time que todos os `{{ var }}` existem no TemplateContext

### WebSocket Gateway

- [ ] **`@Gateway` decorator** — classe com `@Subscribe("event")` para WebSocket
- [ ] **Rooms/channels** — `client.join("room")`, `client.room("room").broadcast(msg)`
- [ ] **`on_connect` / `on_disconnect` hooks**
- [ ] **DI nos Gateways** — `@injectable` services injetáveis em classes `@Gateway`

---

## 🟢 Baixa Prioridade / Roadmap Futuro (v0.4.0+)

### CLI — Generators adicionais

- [ ] **`aura generate component <name>`** — gera Component class + template HTML juntos
- [ ] **`aura generate resource <name> --crud --db`** — model + migration + CRUD com Repository
- [ ] **`aura generate middleware <name>`** — middleware stub

### GraphQL (opcional)

- [ ] **`GraphQLModule.for_root(schema)`** — integração com Strawberry
- [ ] **`/graphql` endpoint** com playground
- [ ] **Subscriptions** via WebSocket

### gRPC (opcional)

- [ ] **`@GrpcController`** — controller que responde gRPC ao lado de HTTP na mesma porta
- [ ] **Code generation** a partir de `.proto`

### Multi-tenancy

- [ ] **`TenantStrategy.ROW_LEVEL`** — coluna `tenant_id` em todas as tabelas
- [ ] **`TenantStrategy.SCHEMA`** — schema PostgreSQL por tenant
- [ ] **`TenantResolver`** — extrair tenant de header, subdomínio ou JWT

### Admin Panel

- [ ] **`AdminModule`** — interface administrativa auto-gerada a partir dos models
- [ ] **`@AdminResource`** — `list_display`, `search_fields`, `filters` declarativos
- [ ] **CRUD automático** no admin a partir do schema Pydantic

### Plugin System

- [ ] **`AuraPlugin` interface** — `on_startup`, `on_shutdown`, acesso ao container
- [ ] **`RedisPlugin`** — connection pool automático
- [ ] **`S3Plugin`** — client AWS S3 pré-configurado
- [ ] **`SentryPlugin`** — error tracking automático

---

## 🔧 Melhorias Técnicas

### Performance

- [ ] **`msgspec` como serialização alternativa** — 10x mais rápido que Pydantic para
  request/response simples (manter Pydantic para validação de entrada)
- [ ] **Route caching** — cache de rotas compiladas para evitar recompilação a cada startup
- [ ] **Template bytecode cache** — `jinja2.BytecodeCache` para produção

### DI Container

- [ ] **Circular dependency detection** — erro claro e descritivo ao invés de `RecursionError`
- [ ] **Lazy providers** — instanciar apenas quando primeiro solicitado
- [ ] **Scoped container por request HTTP** — middleware que cria scope e injeta em `request.state.container`

### Testing

- [ ] **`AuraTestCase`** — base class com helpers para testes de integração
- [ ] **`mock_service(SomeService, replacement)`** — substituir service no container em testes
- [ ] **`snapshot_testing()`** — assert de HTML renderizado contra snapshot

### Observabilidade

- [ ] **`X-Query-Count` header** — contar queries SQL por request em modo debug
- [ ] **N+1 detector middleware** — logar aviso quando > N queries no mesmo request
- [ ] **OpenTelemetry integration** — traces/metrics automáticos
- [ ] **Structured logging** — `structlog` ou `python-json-logger` configurado por padrão

### Docs & DX

- [ ] **`docs/` website** — deploy em GitHub Pages com MkDocs Material
- [ ] **Exemplos completos** — `examples/todo-app`, `examples/blog`, `examples/ecommerce`
- [ ] **Benchmarks** — comparação com FastAPI, Django, Litestar
- [ ] **VSCode Extension** — snippets e goto-definition para decorators Aura

---

## 📦 PyPI & Distribuição

- [ ] **Revogar token PyPI exposto** — token foi exposto em log de sessão anterior;
  gerar novo em https://pypi.org/manage/account/token/
- [ ] **CI/CD com GitHub Actions** — rodar testes + build + publish automático em tags
- [ ] **Badges dinâmicos no README** — cobertura de testes, versão PyPI, downloads/mês
- [ ] **`CHANGELOG.md`** — seguindo Keep a Changelog
- [ ] **v0.1.1** — publicar com `@html`/`@sse` router integration + CLI fixes

---

## 🐛 Bugs conhecidos

| Bug | Arquivo | Impacto | Workaround |
|---|---|---|---|
| `AuraTemplateModule.on_startup` não é chamado automaticamente | `aura/modules/registry.py` | Alto | Chamar `set_engine(engine)` manualmente na startup |
| `aura migrate make` lança NotImplementedError | `aura/cli/commands/migrate.py` | Alto | Usar Alembic diretamente |
| `aura worker` não processa filas SAQ | `aura/cli/commands/worker.py` | Alto | Usar MemoryBackend em dev; SAQ direto em prod |
| Path params sem `Annotated[T, Param()]` não são resolvidos | `aura/routing/router.py` | Médio | Sempre usar `Annotated[int, Param()]` |
| `_send` é atributo privado do Starlette acessado em `_resolve_params` | `aura/routing/router.py` | Baixo | Usa `getattr(request, "_send", None)` com fallback |

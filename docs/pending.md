# Pendências — Tudo que falta construir e melhorar

> Lista completa e atualizada de itens pendentes no Aura Framework.  
> Atualizado em 2026-05-28. Organizado por prioridade e área.
> **243 testes passando · ruff clean · mypy strict 77 arquivos**

---

## ✅ Recentemente concluído (v0.3.0 em progresso)

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
- [x] **`injectable` type inference** — fix de `-> Any` via `@overload`; IDE agora mostra tipo
  correto em classes decoradas com `@injectable`
- [x] **mypy strict** — 0 erros em 74 arquivos (`Success: no issues found`)
- [x] **GitHub Actions CI** — jobs: test (Python 3.10/3.12) → typecheck → lint
- [x] **Makefile** — `make test`, `make typecheck`, `make lint`, `make check`
- [x] **`bulk_update` / `bulk_delete`** — métodos batch no `Repository[T]`
- [x] **`models.py` + `repositories.py` no scaffold** — ambos `aura new` e `aura generate module`
  geram esses arquivos comentados mostrando o padrão correto (`model = User` como class attr,
  `AuraModel` com `__tablename__`, uso de `db.session()` no service)
- [x] **`AuraModel` exposto em `from aura import AuraModel`** — import opcional, silencioso se
  SQLAlchemy não estiver instalado
- [x] **`AuraModel.__abstract__ = True`** — separação em `_AuraRegistry(DeclarativeBase)` +
  `AuraModel(_AuraRegistry, __abstract__=True)`; habilita modelos abstratos intermediários
  sem quebrar `AuraModel.metadata`
- [x] **`aura migrate` completo** — `init` gera `alembic.ini` + `env.py` sem subprocess;
  `make` aceita mensagem opcional (padrão = timestamp); `up`, `down`, `stamp`, `status`;
  spinners Rich + painéis coloridos de sucesso/erro; 37 testes
- [x] **`JWTGuard`** — valida `Authorization: Bearer` com `python-jose`; popula
  `request.state.user`; suporta `auto_error=False`; extra `[jwt]` já existia
- [x] **`RateLimitGuard`** — Guard por rota (sliding window, só stdlib); complementa o
  `RateLimitMiddleware` global existente; raises 429 via `on_denied`
- [x] **`SessionMiddleware`** — sessões assinadas em cookie via `itsdangerous`; carrega em
  `request.state.session`; nova extra `[session]`; 11 testes integração
- [x] **`DatabaseManager` no ciclo de vida do app** — lê `AURA__DATABASE__URL` na startup e
  chama `db.init()` automaticamente; backward-compatible (sem env var = comportamento anterior)
- [x] **`AuraTemplateModule.on_startup` integrado** — `ModuleRegistry.run_module_startups()`
  itera todos os módulos e chama `on_startup(container, debug)` se definido (sync e async)
- [x] **`url_for()` global no Jinja2** — `AuraTemplateEngine.register_routes(routes)` registra
  closure `url_for(name, **params)` substituindo `{param}` no path; wired automaticamente no build
- [x] **SAQ backend auto-detectado** — detecta `AURA__JOBS__BROKER_URL`; sem env var → `MemoryBackend`;
  com URL → `SAQBackend(redis_url=...)` instanciado lazy
- [x] **`aura worker` funcional** — `AuraWorker.run()` detecta SAQ e usa o worker nativo SAQ com
  `TaskRegistry`; CLI ganhou `--broker-url` como alternativa ao env var
- [x] **`Repository.paginate()`** — retorna `Page[T]` com `items`, `total`, `page`, `per_page`,
  `has_next`; roda COUNT + SELECT separados; exportado em `aura` e `aura.orm`
- [x] **`async with db.transaction()`** — unit-of-work semântico; alias de `db.session()` para
  operações em múltiplos repositórios dentro de uma transação
- [x] **`aura generate module --with-db`** — flag descomenta `models.py` e `repositories.py` com
  código real (`AuraModel` + `Repository[T]`); sem flag = stubs comentados (comportamento atual)

---

## 🟡 Média Prioridade (v0.3.0 — restante)

### Guards & Auth

- [x] ~~`JWTGuard`~~ ✓ concluído  
- [x] ~~`RateLimitGuard`~~ ✓ concluído  
- [x] ~~`SessionMiddleware`~~ ✓ concluído

### Routing — DX

- [ ] **Inferência automática de `Param()` para path params** — `async def get_user(self, user_id: int)`
  deveria deduzir `Param()` quando `user_id` aparece no path `/{user_id}`, sem precisar de
  `Annotated[int, Param()]`
- [ ] **`response_model` para serialização estrita** — `@get("/", response=UserResponse)` deveria
  garantir que apenas campos do schema são retornados (como FastAPI faz)

### DI Container

- [ ] **Scoped container por request HTTP** — middleware que cria scope e injeta `AsyncSession`
  automaticamente via `request.state.container`; habilita `def __init__(self, session: AsyncSession)`
  sem `async with db.session()` manual

### Interceptors

- [ ] **Interface `Interceptor`** — `before(context) / after(context, response)` pipeline
- [ ] **`LoggingInterceptor`** — log de método, path, status e duração em cada request

---

## 🟢 Baixa Prioridade / Roadmap Futuro (v0.4.0+)

### Templates — features avançadas

- [ ] **`static()` tag com `StaticFiles` real** — hoje retorna `/static/{path}` hardcoded
- [ ] **Middleware de auto-reload de templates** — usar `watchfiles` em dev
- [ ] **Islands Architecture** — hidratação seletiva com React/Vue/Svelte
- [ ] **Email templates** — integração com SMTP/SendGrid

### WebSocket Gateway

- [ ] **`@Gateway` decorator** — classe com `@Subscribe("event")` para WebSocket
- [ ] **Rooms/channels** — `client.join("room")`, `client.room("room").broadcast(msg)`
- [ ] **DI nos Gateways** — `@injectable` services injetáveis em classes `@Gateway`

### CLI — Generators adicionais

- [ ] **`aura generate resource <name> --crud --db`** — model + migration + CRUD completo
- [ ] **`aura generate middleware <name>`** — middleware stub
- [ ] **`aura generate component <name>`** — Component class + template HTML juntos

### GraphQL / gRPC / Multi-tenancy / Admin Panel

- [ ] **`GraphQLModule.for_root(schema)`** — integração com Strawberry
- [ ] **`@GrpcController`** — controller gRPC ao lado de HTTP
- [ ] **`TenantStrategy.ROW_LEVEL / SCHEMA`** — isolamento por tenant
- [ ] **`AdminModule`** — interface administrativa auto-gerada

---

## 🔧 Melhorias Técnicas

### Performance

- [ ] **`msgspec` como serialização alternativa** — 10x mais rápido que Pydantic para respostas simples
- [ ] **Template bytecode cache** — `jinja2.BytecodeCache` para produção

### Testing

- [ ] **`AuraTestCase`** — base class com helpers para testes de integração
- [ ] **`mock_service(SomeService, replacement)`** — substituir service no container em testes

### Observabilidade

- [ ] **`X-Query-Count` header** — contar queries SQL por request em modo debug
- [ ] **OpenTelemetry integration** — traces/metrics automáticos
- [ ] **Structured logging** — `structlog` configurado por padrão

### Docs & DX

- [ ] **`docs/` website** — deploy em GitHub Pages com MkDocs Material
- [ ] **Exemplos completos** — `examples/todo-app`, `examples/blog`, `examples/ecommerce`
- [ ] **Benchmarks** — comparação com FastAPI, Django, Litestar

---

## 📦 PyPI & Distribuição

- [ ] **Revogar token PyPI exposto** — token foi exposto em log de sessão anterior;
  gerar novo em https://pypi.org/manage/account/token/
- [ ] **Badges dinâmicos no README** — cobertura de testes, versão PyPI, downloads/mês
- [ ] **`CHANGELOG.md`** — seguindo Keep a Changelog
- [ ] **v0.2.0** — publicar com bulk ops, scaffold com models/repos, AuraModel abstract fix

---

## 🐛 Bugs conhecidos

| Bug | Arquivo | Impacto | Workaround |
|---|---|---|---|
| `AuraTemplateModule.on_startup` não é chamado automaticamente | `aura/modules/registry.py` | Alto | Chamar `set_engine(engine)` manualmente na startup |
| `aura migrate make` lança NotImplementedError | `aura/cli/commands/migrate.py` | Alto | Usar Alembic diretamente |
| `aura worker` não processa filas SAQ | `aura/cli/commands/worker.py` | Alto | Usar MemoryBackend em dev; SAQ direto em prod |
| Path params sem `Annotated[T, Param()]` não são resolvidos | `aura/routing/router.py` | Médio | Sempre usar `Annotated[int, Param()]` |

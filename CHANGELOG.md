# Changelog

All notable changes to Aura Framework are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

_Nothing yet._

---

## [1.4.0] — Waves 4–6

> **Nota de release:** A versão **1.3.0** foi publicada no PyPI a partir do commit órfão `8989544` (branch divergente). Esta release **1.4.0** consolida as waves 4–6 em `main` e substitui o histórico de pacote.

### Wave 4 — DX & Observabilidade

#### Added

- **Rate limit backends:** abstração `RateLimitBackend` com `MemoryBackend` (padrão) e `RedisBackend` para rate limit distribuído multi-processo (`pip install "aura-web[redis]"`).
- **OpenAPI:** `JWTGuard` registra `BearerAuth` em `components.securitySchemes` e `security` nas operações protegidas.
- **OpenAPI:** `Router(tags=[...])` faz merge com tags de rota, sem duplicatas.
- **RequestLogInterceptor:** redação de headers sensíveis (`authorization`, `cookie`, etc.) quando `log_headers=True` (middleware ASGI e interceptor de rota).

#### Changed

- **RateLimitMiddleware** e **RateLimitGuard:** contadores delegados a `RateLimitBackend` injetável (memória ou Redis).

### Wave 5 — Contract Cleanup

#### Added

- **FormData:** binding explícito de `FormDataMarker` no plano de parâmetros de rota.
- **Interceptors:** `global_interceptors` e `route_middleware` integrados ao pipeline de handlers (JSON, HTML, SSE, WebSocket).
- **HTTP 422:** `UnprocessableEntityException` com corpo estruturado para erros de validação.

#### Changed

- **Router:** middleware por rota aplicado de forma consistente em todos os tipos de resposta.
- **ModuleRegistry:** exports e prefixo global alinhados ao contrato público.
- **Interceptors:** `ChainRequestLogInterceptor` e exports públicos consolidados em `aura.interceptors`.

#### Removed

- **`RequestPipeline`:** módulo morto `aura/core/pipeline.py` removido — o roteamento usa wrappers diretos no `Router` ([ADR-003](docs/decisions/ADR-003-contract-cleanup.md)).

### Wave 6 — Admin Consolidation

#### Added

- **`ModelForm`:** mapeamento automático de colunas SQLAlchemy → campos `AuraForm` para CRUD no admin ([ADR-004](docs/decisions/ADR-004-admin-modelform.md)).
- **Admin CSRF:** token em formulários de mutação via htmx.

#### Changed

- **Admin views:** parsing duplicado de formulário removido; delegação a `ModelForm.save()`.

---

## [1.3.0] — Wave 3

> Publicada a partir do commit órfão `8989544` (não reflete o estado atual de `main`).

### Added

- **RateLimitGuard:** headers `X-RateLimit-Limit`, `X-RateLimit-Remaining` e `Retry-After` em respostas **429** (alinhado ao `RateLimitMiddleware`).
- **RateLimitGuard:** parâmetro `max_tracked_keys` com eviction LRU para limitar uso de memória.
- **AuraWorker (SAQ):** flags CLI `--queue` / `-q` e `--burst` / `-b` repassadas ao worker nativo do SAQ.
- **TaskRegistry:** método `clear()` + fixture de teste para isolamento entre testes.

### Changed

- **DatabaseMiddleware:** fail-fast — se a lazy-init do banco falhar, a requisição retorna **500** com mensagem acionável em vez de prosseguir sem sessão.
- **Templates:** `component()` é assíncrono; em templates Jinja2 use `{{ await component(...) }}` (ver [ADR-002](docs/decisions/ADR-002-async-templates-only.md)).

### Fixed

- **AuraWorker:** `queues` e `burst` eram ignorados no path SAQ; agora respeitados.
- **mypy:** erros residuais em `aura/` zerados.
- **test_tinker:** falhas de isolamento corrigidas.

### Breaking changes

#### C15 — `await component(...)` obrigatório em templates

Removido o wrapper síncrono `_render_component_sync()` que usava `run_until_complete()` (risco de deadlock).

```diff
- {{ component('button', label='Click') }}
+ {{ await component('button', label='Click') }}
```

Em loops e condicionais, adicione `await` em cada chamada. Ver [ADR-002](docs/decisions/ADR-002-async-templates-only.md).

---

## [1.2.0] — Waves 1–2

### Security & contract hardening (Wave 1)

- Routing: coerção inválida de parâmetros → **422** (não 500).
- `QuerySet.delete()` exige `allow_unfiltered=True` sem filtros ([ADR-001](docs/decisions/ADR-001-security-hardening.md)).
- `redirect()` aceita apenas paths relativos (`/…`).
- Logs de startup redactam secrets.
- Extra `[jwt]` migra para **PyJWT** (não `python-jose`).
- `RateLimitMiddleware`: janela atômica + headers `X-RateLimit-*`.

### DI, SAQ, Admin, qualidade (Wave 2)

- `@inject` / `Annotated[T, inject()]` no DI.
- SAQ: `Queue.from_url`, `timeout`/`scheduled` em segundos.
- Admin: PBKDF2-HMAC-SHA256, CSRF em mutações, logout via POST.
- `mypy` em `tests/` (0 erros).

---

## [1.0.0] — Initial public release

- Core ASGI, routing, DI, ORM async, guards, jobs, templates, CLI.

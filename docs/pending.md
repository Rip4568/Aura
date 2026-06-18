# Roadmap Aura — `docs/pending.md`

> Fonte da verdade para priorização. Marque `[x]` **somente** após verificar no código (`grep`) e nos testes.

**Branch atual:** `fix/wave11-message-brokers`  
**Baseline de testes (2026-06-17):** 713 passed · 4 skipped · mypy `aura/` + `tests/` 0 erros · ruff clean · cobertura `aura/` ≥ 75%  
**Versão:** `1.5.0` (`pyproject.toml`)

---

## Wave 1 — Security & Contract Hardening ✅

Commits `51b63f6` … `3d85c9a` (7 commits desde `main`).

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W1-R1 | Routing: coerção inválida de query/path/header/cookie → **422** (não 500) | [x] | `aura/routing/router.py` |
| W1-R2 | Routing: body obrigatório e Content-Type validados → **422** | [x] | `aura/routing/router.py` |
| W1-O1 | ORM: `QuerySet.last()` respeita `order_by()` anterior | [x] | `aura/orm/query.py` |
| W1-O2 | ORM: `delete(allow_unfiltered=True)` — **breaking change** | [x] | `aura/orm/query.py`, ADR-001 |
| W1-S1 | Startup: logs de config redactam secrets (`***`) | [x] | `aura/core/app.py` |
| W1-S2 | `redirect()` bloqueia open redirect (só paths relativos `/…`) | [x] | `aura/core/response.py` |
| W1-J1 | Extra `[jwt]`: `python-jose` → **PyJWT** | [x] | `pyproject.toml`, `aura/guards/jwt.py` |
| W1-J2 | `JWTGuard`: validação rigorosa de claims (`exp`, `alg`, etc.) | [x] | `aura/guards/jwt.py` |
| W1-M1 | `RateLimitMiddleware`: janela atômica (`asyncio.Lock`) | [x] | `aura/middleware/rate_limit.py` |
| W1-M2 | `RateLimitMiddleware`: headers `X-RateLimit-*` e `Retry-After` | [x] | `aura/middleware/rate_limit.py` |
| W1-M3 | `DIRequestScopeMiddleware`: cleanup de escopo em `finally` | [x] | `aura/middleware/di.py` |
| W1-M4 | `Aura(prefix=…)` aplicado ao roteamento global | [x] | `aura/core/app.py`, `aura/modules/registry.py` |

---

## Wave 2 — DI, SAQ, Migrations, Admin, Qualidade ✅

Concluída na branch `fix/wave2-inject-saq-admin-mypy`.

| ID | Item | Status | Notas |
|----|------|--------|-------|
| W2-A2 | `@inject` / `Annotated[T, inject()]` no DI | [x] | `aura/di/decorators.py`, `aura/di/container.py` |
| W2-C7 | SAQ: `Queue.from_url` em vez de instanciar classe abstrata | [x] | `aura/jobs/backends/saq_backend.py` |
| W2-C7b | SAQ: `timeout` e `scheduled` em **segundos** (epoch) | [x] | `aura/jobs/backends/saq_backend.py` |
| W2-C11 | `generate_env_py` sem `os.walk` / auto-discovery inseguro | [x] | `aura/orm/migrations.py` |
| W2-C13 | Admin: senhas com **PBKDF2-HMAC-SHA256** | [x] | `aura/admin/security.py` |
| W2-C14 | Admin: tokens **CSRF** em mutações (htmx `X-CSRF-Token`) | [x] | `aura/admin/security.py`, `aura/admin/views.py` |
| W2-C14b | Admin: logout via **POST** `/admin/logout` | [x] | `aura/admin/views.py`, `layout.html` |
| W2-A20 | mypy em `tests/` | [x] | `pyproject.toml` overrides; 0 erros em `mypy tests/` |

---

## Wave 3 — Produção & Estabilidade ✅

Concluída na branch `fix/wave3-production-stability`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W3-C12 | `DatabaseMiddleware` fail-fast (500 se lazy-init falhar) | [x] | `aura/orm/middleware.py`, `tests/test_orm.py` |
| W3-C15 | Templates: remover `_render_component_sync`, exigir `await component(...)` | [x] | `aura/templates/engine.py`, ADR-002 |
| W3-C3 | `RateLimitGuard`: LRU (`max_tracked_keys`) + headers 429 | [x] | `aura/guards/rate_limit.py`, `tests/test_guards_auth.py` |
| W3-A7 | `AuraWorker`: repassar `queues`/`burst` ao SAQ | [x] | `aura/jobs/worker.py`, `tests/test_jobs_worker.py` |
| W3-A8 | `TaskRegistry.clear()` + fixture de isolamento | [x] | `aura/jobs/base.py`, `tests/conftest.py` |
| W3-M1 | mypy `aura/` — 0 erros residuais | [x] | `python -m mypy aura/` |
| W3-T1 | `test_tinker` — falhas corrigidas | [x] | `tests/test_tinker.py` |

**Breaking change:** C15 — ver [ADR-002](decisions/ADR-002-async-templates-only.md) e `CHANGELOG.md`.

---

## Wave 4 — DX & Observabilidade ✅

Concluída na branch `fix/wave4-dx-observability`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W4-O1 | OpenAPI: `securitySchemes` — `JWTGuard` expõe `BearerAuth` em `/docs` | [x] | `aura/guards/jwt.py`, `aura/schema/openapi.py` |
| W4-O2 | OpenAPI: merge de `Router.tags` com tags de rota (sem duplicatas) | [x] | `aura/routing/router.py`, `tests/test_openapi.py` |
| W4-R1 | Rate limit: backend Redis compartilhado (`RateLimitBackend` + `RedisBackend`) | [x] | `aura/middleware/rate_limit_backends/` |
| W4-L1 | `RequestLogInterceptor`: redação de headers sensíveis (`log_headers=True`) | [x] | `aura/logging/interceptor.py`, `tests/test_logging.py` |

---

## Wave 5 — Contract Cleanup ✅

Concluída na branch `fix/wave5-contract-cleanup`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W5-R1 | `FormDataMarker` no plano de binding de parâmetros | [x] | `aura/routing/router.py`, `tests/test_routing.py` |
| W5-R2 | Interceptors + middleware por rota em todos os `response_type` | [x] | `aura/routing/router.py`, `tests/test_middleware.py` |
| W5-C1 | Remover `RequestPipeline` morto (`aura/core/pipeline.py`) | [x] | ADR-003 |
| W5-E1 | `UnprocessableEntityException` (422) estruturada | [x] | `aura/exceptions/http.py`, `tests/test_exceptions.py` |
| W5-M1 | Exports e `ModuleRegistry` alinhados ao contrato público | [x] | `aura/modules/registry.py`, `tests/test_modules.py` |

Ver [ADR-003](decisions/ADR-003-contract-cleanup.md).

---

## Wave 6 — Admin Consolidation ✅

Concluída na branch `fix/wave6-admin-consolidation`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W6-A1 | `ModelForm` — mapeamento SQLAlchemy → `AuraForm` | [x] | `aura/forms/modelform.py` |
| W6-A2 | Admin views delegam a `ModelForm` (sem parsing duplicado) | [x] | `aura/admin/views.py`, `tests/test_admin.py` |
| W6-A3 | CSRF token em template de formulário admin | [x] | `aura/admin/templates/form.html` |

Ver [ADR-004](decisions/ADR-004-admin-modelform.md).

---

## Wave 7 — Infra & Release ✅

Concluída na branch `fix/wave7-infra-release`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W7-1 | Versão `1.4.0` + `CHANGELOG.md` consolidado | [x] | `pyproject.toml`, `CHANGELOG.md` |
| W7-2 | CI: Python 3.11/3.13, mypy tests, cobertura ≥ 75% | [x] | `.github/workflows/ci.yml` |
| W7-3 | Fixtures autouse: reset `db` + `container`; `db_manager` centralizado | [x] | `tests/conftest.py` |
| W7-4 | `.pre-commit-config.yaml` (ruff + mypy) | [x] | `.pre-commit-config.yaml` |
| W7-5 | Makefile Windows-friendly (`python` em vez de `python3`) | [x] | `Makefile` |
| W7-6 | Docs: `tinker.md`, ADR-003/004, `pending.md`, `CLAUDE.md` | [x] | `docs/` |
| W7-7 | MkDocs skeleton (`mkdocs.yml` + `docs/index.md`) | [x] | `mkdocs.yml` |

---

## Wave 8 — Security & Proxy Hardening ✅

Concluída na branch `fix/wave7-infra-release`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W8-1 | `trusted_proxies` em RateLimitMiddleware, RateLimitGuard e `AuraConfig` | [x] | `aura/middleware/rate_limit.py`, `aura/guards/rate_limit.py`, `aura/config/base.py`, `tests/test_client_ip.py` |
| W8-2 | Redis backend: script Lua atômico (sliding window sem race) | [x] | `aura/middleware/rate_limit_backends/redis.py`, `tests/test_rate_limit_redis.py` |
| W8-3 | `JWTGuard(require_exp=True)` por padrão — **breaking** | [x] | `aura/guards/jwt.py`, `tests/test_guards_auth.py` |
| W8-4 | `SessionMiddleware`: `Set-Cookie` só quando sessão mutada + `HttpOnly` | [x] | `aura/middleware/session.py`, `tests/test_guards_auth.py` |
| W8-5 | `UnprocessableEntityException.to_dict()` — formato 422 FastAPI | [x] | `aura/exceptions/http.py`, `tests/test_exceptions.py` |
| W8-6 | `Aura(interceptors=[...])` — API global de interceptors | [x] | `aura/core/app.py`, `aura/interceptors/`, `tests/test_interceptors.py` |
| W8-7 | Middleware factory via `Aura(middleware=[CORSMiddleware(...)])` | [x] | `aura/core/app.py`, `tests/test_middleware.py` |

---

## Wave 9 — Database Jobs (sem Redis) ✅

Concluída na branch `fix/wave9-database-jobs`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W9-1 | `DatabaseBackend` — fila persistente em SQL (`aura_jobs`) | [x] | `aura/jobs/backends/database.py`, `tests/test_database_backend.py` |
| W9-2 | Modelo `AuraJob` com status, retry, scheduled_at | [x] | `aura/jobs/models.py`, `tests/test_database_backend.py` |
| W9-3 | `AURA__JOBS__BACKEND=database` auto-seleciona backend | [x] | `aura/jobs/decorators.py`, `aura/config/base.py` (`JobsConfig.backend`) |
| W9-4 | `AuraWorker` — polling DB com claim, retry e mark success/failed | [x] | `aura/jobs/worker.py`, `tests/test_database_backend.py` |
| W9-5 | Requer `[sqlalchemy]` — lazy import com hint de instalação | [x] | `aura/jobs/backends/database.py`, `pyproject.toml` |

---

## Wave 10 — EventBus ✅

Concluída na branch `fix/wave10-event-bus`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W10-1 | Contrato `EventBus` + `EventEnvelope` (topic, payload, event_id, timestamp) | [x] | `aura/events/base.py` |
| W10-2 | `InMemoryEventBus` — fan-out in-process (dev/test) | [x] | `aura/events/backends/memory.py`, `tests/test_events.py` |
| W10-3 | `RedisStreamsEventBus` — `XADD` / `XREADGROUP` com prefixo configurável | [x] | `aura/events/backends/redis_streams.py`, `tests/test_events.py` |
| W10-4 | `@on_event("topic")` + `EventHandlerRegistry` + wiring no startup | [x] | `aura/events/decorators.py`, `aura/events/wiring.py`, `tests/test_events.py` |
| W10-5 | `EventsConfig` opt-in (`events.enabled=False` por padrão) | [x] | `aura/config/base.py`, `tests/test_events.py::TestEventsConfig` |
| W10-6 | `AuraEventsModule.for_root()` + auto-wiring em `Aura._on_startup` | [x] | `aura/events/module.py`, `aura/events/lifecycle.py`, `aura/core/app.py` |
| W10-7 | ADR-006 — decisões de arquitetura EventBus | [x] | `docs/decisions/ADR-006-event-bus.md` |

---

## Wave 11 — Message Brokers (RabbitMQ / Kafka) ✅

Concluída na branch `fix/wave11-message-brokers`.

| ID | Item | Status | Verificação |
|----|------|--------|-------------|
| W11-1 | `RabbitMQEventBus` — exchange `topic`, routing key = tópico | [x] | `aura/events/backends/rabbitmq.py`, `tests/test_rabbitmq_events.py` |
| W11-2 | `KafkaEventBus` — producer/consumer `aiokafka`, commit manual | [x] | `aura/events/backends/kafka.py`, `tests/test_kafka_events.py` |
| W11-3 | `@EventPattern` (fire-and-forget) e `@MessagePattern` (request/response) | [x] | `aura/events/microservice.py`, `tests/test_message_patterns.py` |
| W11-4 | `MessagingClient` — `emit()` e `send()` com timeout | [x] | `aura/events/client.py`, `tests/test_message_patterns.py` |
| W11-5 | Extras `[rabbitmq]` (`aio-pika`) e `[kafka]` (`aiokafka`) | [x] | `pyproject.toml`, `tests/test_rabbitmq_events.py`, `tests/test_kafka_events.py` |
| W11-6 | `EventsConfig` estendida (`rabbitmq_url`, `kafka_bootstrap_servers`, etc.) | [x] | `aura/config/base.py`, `aura/events/wiring.py` |
| W11-7 | ADR-007 — decisões de arquitetura message brokers | [x] | `docs/decisions/ADR-007-message-brokers.md` |

---

## Pendentes pós-hardening

Itens **não** cobertos pelas waves 1–11.

### Médio / baixo

- [ ] `QuerySet.explain()` — concatenação de SQL (preferir binding parametrizado)
- [ ] `CompressionMiddleware` — `gzip_level` ignorado
- [ ] Site MkDocs publicado no GitHub Pages (skeleton pronto; deploy pendente)
- [ ] `AdminModule` auto-gerado (roadmap v0.4+)

---

## Breaking changes documentados

| Mudança | Migração |
|---------|----------|
| `QuerySet.delete()` / `Repository` sem filtros | Passar `allow_unfiltered=True` explicitamente |
| Extra `[jwt]` | `pip install "aura-web[jwt]"` instala **PyJWT**, não `python-jose` |
| `redirect(url)` | Apenas URLs relativas (`/path`); URLs absolutas lançam `BadRequestException` |
| `component(...)` em templates Jinja2 (v1.3.0) | Usar `{{ await component(...) }}` — ver ADR-002 |
| Erros **422** (v1.4.0) | Corpo `{detail: [{loc, msg, type}]}` — ajustar parsers de cliente |
| `JWTGuard` sem `exp` (v1.4.0) | Tokens sem claim `exp` rejeitados; use `require_exp=False` se necessário |
| `SessionMiddleware` cookie (v1.4.0) | Cookie só reenviado quando sessão mutada; inclui `HttpOnly` |

Ver `docs/decisions/ADR-001-security-hardening.md` e `docs/decisions/ADR-002-async-templates-only.md`.  
Release notes: `CHANGELOG.md`.

---

## Comandos de verificação

```bash
python -m pytest tests/ -q --tb=no
python -m mypy aura/ --ignore-missing-imports
python -m mypy tests/ --ignore-missing-imports
python -m ruff check aura/ tests/
```

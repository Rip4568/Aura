# Roadmap Aura — `docs/pending.md`

> Fonte da verdade para priorização. Marque `[x]` **somente** após verificar no código (`grep`) e nos testes.

**Branch atual:** `fix/wave7-infra-release`  
**Baseline de testes (2026-06-17):** 658 passed · 2 skipped · mypy `aura/` + `tests/` 0 erros · ruff clean · cobertura `aura/` ≥ 75%  
**Versão:** `1.4.0` (`pyproject.toml`)

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

## Pendentes pós-hardening

Itens **não** cobertos pelas waves 1–7.

### Médio / baixo

- [ ] `QuerySet.explain()` — concatenação de SQL (preferir binding parametrizado)
- [ ] `SessionMiddleware` — reenvio de cookie em toda resposta
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

# Roadmap Aura — `docs/pending.md`

> Fonte da verdade para priorização. Marque `[x]` **somente** após verificar no código (`grep`) e nos testes.

**Branch atual:** `fix/wave2-inject-saq-admin-mypy`  
**Baseline de testes (2026-06-17):** 611 passed · 2 skipped · mypy `tests/` 0 erros · ruff clean
**Versão:** `1.2.0` (`pyproject.toml`)

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
| W2-A2 | `@inject` / `Annotated[T, inject()]` no DI | [x] | `aura/di/decorators.py`, `aura/di/container.py` (`_parse_dependency_type`); override por `param_name` ainda não consumido |
| W2-C7 | SAQ: `Queue.from_url` em vez de instanciar classe abstrata | [x] | `aura/jobs/backends/saq_backend.py` |
| W2-C7b | SAQ: `timeout` e `scheduled` em **segundos** (epoch) | [x] | `aura/jobs/backends/saq_backend.py` |
| W2-C11 | `generate_env_py` sem `os.walk` / auto-discovery inseguro | [x] | `aura/orm/migrations.py` — exige import explícito ou placeholder comentado |
| W2-C13 | Admin: senhas com **PBKDF2-HMAC-SHA256** | [x] | `aura/admin/security.py` |
| W2-C14 | Admin: tokens **CSRF** em mutações (htmx `X-CSRF-Token`) | [x] | `aura/admin/security.py`, `aura/admin/views.py`, templates |
| W2-C14b | Admin: logout via **POST** `/admin/logout` | [x] | `aura/admin/views.py`, `layout.html` |
| W2-A20 | mypy em `tests/` | [x] | `pyproject.toml` overrides; 0 erros em `mypy tests/` |

---

## Pendentes pós-hardening (análise 2026-06-16)

Itens críticos/altos **não** cobertos pelas waves 1–2.

### Crítico / alto

- [ ] `RateLimitGuard` — estado em memória, sem headers padrão (middleware já melhorado)
- [ ] `DatabaseMiddleware` — prossegue sem sessão se lazy init falhar
- [ ] Componentes síncronos em templates async (`aura/templates/engine.py`)
- [ ] `AuraWorker` ignora `queues`/`burst` no path SAQ
- [ ] `TaskRegistry` singleton global — isolamento fraco entre testes
- [ ] Admin: reutilizar `AuraForm`/`ModelForm` (duplicação de parsing)
- [ ] OpenAPI: `securitySchemes` e merge de `Router.tags`
- [ ] Backend Redis compartilhado para rate limit multi-processo

### Médio / baixo

- [ ] `QuerySet.explain()` — concatenação de SQL
- [ ] `SessionMiddleware` — reenvio de cookie em toda resposta
- [ ] `CompressionMiddleware` — `gzip_level` ignorado
- [ ] `RequestLogInterceptor` — redação de headers/body sensíveis
- [ ] CI: cobertura mínima e Python 3.11/3.13
- [ ] Site MkDocs + GitHub Pages
- [ ] `AdminModule` auto-gerado (roadmap v0.4+)

---

## Breaking changes documentados

| Mudança | Migração |
|---------|----------|
| `QuerySet.delete()` / `Repository` sem filtros | Passar `allow_unfiltered=True` explicitamente |
| Extra `[jwt]` | `pip install "aura-web[jwt]"` instala **PyJWT**, não `python-jose` |
| `redirect(url)` | Apenas URLs relativas (`/path`); URLs absolutas lançam `BadRequestException` |

Ver `docs/decisions/ADR-001-security-hardening.md`.

---

## Comandos de verificação

```bash
python -m pytest tests/ -q --tb=no
python -m mypy aura/ --ignore-missing-imports
python -m mypy tests/ --ignore-missing-imports   # wave 2 — em progresso
python -m ruff check aura/ tests/
```

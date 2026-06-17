# Análise Completa do Framework Aura — Relatório Consolidado

**Projeto:** Aura Web (`aura-web` 1.2.0)  
**Branch analisado:** `main`  
**Diretório:** `C:/Users/jonathas/Desktop/things/codes/Aura`  
**Data:** 2026-06-16  
**Metodologia:** Análise orquestrada com 6 subagentes especializados cobrindo arquitetura, ORM/dados, routing/segurança, middleware/jobs, forms/templates/admin/CLI e testes/qualidade.  

---

## 1. Resumo Executivo

O Aura é um framework Python async-first, modular e inspirado no NestJS, com DI, ORM sobre SQLAlchemy 2.x, routing sobre Starlette, jobs, templates, admin e CLI. A proposta é sólida e a base de código já entrega 589 testes passando (~80% de cobertura) em ~12s, com uma API pública atrativa para desenvolvedores.

No entanto, a análise revelou **dezenas de problemas reais**, vários deles críticos para produção: vazamento de segredos em logs, biblioteca JWT depreciada/ vulnerável, rate-limit ineficaz em multi-processo, backend SAQ quebrado com a versão instalada, componentes síncronos em templates async, admin sem hash/CSRF/rate-limit, e uma suite de testes com isolamento fraco e 85 erros de `mypy`. A promessa de "type-safe" e "mypy strict 0 erros" não é atingida hoje.

A boa notícia é que a arquitetura de alto nível é coerente. A maioria dos problemas está em **implementação e integração**, não em conceito. Com um refactoring focado nas áreas críticas, o Aura pode se tornar um framework confiável para produção.

---

## 2. Pontos Fortes (consolidados)

1. **Arquitetura modular e DI funcional** — `@Module`, `DIContainer`, lifetimes (singleton/scoped/transient) e detecção de dependências circulares (`aura/di/`, `aura/modules/`).
2. **ORM fluente e maduro** — `QuerySet`, `Repository[T]`, eager loading (`include`/`select_related`), Q objects, lookups estilo Django, profiling de queries e detecção de N+1 (`aura/orm/`).
3. **Configuração type-safe** — `AuraConfig` com Pydantic Settings, envs aninhadas (`AURA__SERVER__PORT`) e validação de `secret_key` em produção (`aura/config/base.py`).
4. **Routing consistente** — wrappers unificados para HTTP/HTML/SSE/WebSocket, binding automático de parâmetros via `Annotated`, serialização sanitizada de erros (`aura/routing/router.py`).
5. **Testes volumosos e rápidos** — 589 testes usando SQLite `:memory:`, cobrindo a maioria dos módulos.
6. **CLI rica** — scaffolding (`aura new`), servidor, migrations, seeders, worker e REPL (`aura/cli/`).
7. **Documentação OpenAPI automática** com flattening de `$defs` (`aura/schema/openapi.py`).
8. **Segurança de headers padrão** — `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy` (`aura/middleware/security.py`).

---


## 4. Concluído (Waves 1–2 · 2026-06-17)

| ID | Resumo |
|----|--------|
| C1 | Logs de startup redactam secrets |
| C2 | PyJWT + validação de claims |
| C4–C6 | Coerção/body → 422; `redirect()` só paths `/…` |
| C7 | SAQ `Queue.from_url`; timeout/scheduled em segundos |
| C8 | Rate limit middleware atômico + headers |
| C9–C11 | `last()` + `order_by`; delete com `allow_unfiltered`; migrations `env.py` seguro |
| C13–C14 | Admin PBKDF2, CSRF, logout POST |
| A1 | `Aura(prefix=…)` no roteamento |
| A2 | `@inject` / `Annotated[T, inject()]` |
| A14 | DI scope cleanup em `finally` |
| A16 | Params obrigatórios inválidos → 422 |
| A20 | `mypy tests/` — 0 erros |

Ver: `docs/pending.md`, `docs/decisions/ADR-001-security-hardening.md`.

---

## 3. Problemas Críticos (pendentes) 🛑

| # | Problema | Arquivo(s) | Impacto |
|---|----------|------------|---------|
| C3 | **`RateLimitGuard` mantém estado em memória** — cresce sem limpeza, ineficaz em multi-processo, sem headers padrão. | `aura/guards/rate_limit.py` | Negação de serviço, bypass de rate limit. |
| C12 | **`DatabaseMiddleware` prossegue sem sessão** se lazy init falhar. | `aura/orm/middleware.py:61-81` | Requests sem transação gerenciada. |
| C15 | **Componentes síncronos em templates async** — `_render_component_sync` chama `loop.run_until_complete` dentro de loop ativo. | `aura/templates/engine.py:180-189` | RuntimeError em uso real. |
| C16 | **Validação de `SECRET_KEY` em produção bypassa `pytest`** — remoção de `pytest` de `sys.modules` nos testes. | `tests/test_security.py:109-128`, `aura/config/base.py` | Chave insegura pode passar despercebida em produção. |

---

## 4. Problemas de Alto Risco 🔴

| # | Problema | Arquivo(s) |
|---|----------|------------|
| A3 | `RequestPipeline` existe mas não é usado pela aplicação. | `aura/core/pipeline.py` |
| A4 | `ModuleRegistry` não detecta importações cíclicas. | `aura/modules/registry.py:54-80` |
| A5 | `ModuleRegistry` assume controllers sempre como classes. | `aura/modules/registry.py:74-78` |
| A6 | Carregamento de `.env` em `Aura.__init__` polui ambiente de testes. | `aura/core/app.py:28-44` |
| A7 | `AuraWorker` ignora `queues` e `burst` no path SAQ; registra todas as tarefas em qualquer worker. | `aura/jobs/worker.py:109-139` |
| A8 | `TaskRegistry` é singleton global mutável — vazamento de estado entre testes/apps. | `aura/jobs/base.py:141` |
| A9 | `MemoryBackend._results` nunca limpa memória. | `aura/jobs/backends/memory.py:40` |
| A10 | `SessionMiddleware` reenvia cookie em toda resposta e default `https_only=False`. | `aura/middleware/session.py:52, 107-121` |
| A11 | `RequestLogInterceptor` pode logar headers/body sensíveis sem redação. | `aura/interceptors/logging.py:67-94` |
| A12 | `CompressionMiddleware` ignora `gzip_level`. | `aura/middleware/compression.py:29-64` |
| A13 | `RateLimitMiddleware` confia em `X-Forwarded-For` sem proxies confiáveis. | `aura/middleware/rate_limit.py:98-109` |
| A15 | OpenAPI ignora `Router.tags` e não gera `securitySchemes`. | `aura/routing/router.py:304-313`, `aura/schema/openapi.py` |
| A17 | Admin duplica parsing/validação em vez de reutilizar `AuraForm`. | `aura/admin/views.py:315-684` |
| A18 | `.env` gerado pelo scaffolding contém secrets reais. | `aura/cli/commands/new.py:779-788` |
| A19 | Detecção de produção baseada em substring da URL do banco. | `aura/cli/commands/seed.py:172-188` |

---

## 5. Problemas de Risco Médio 🟡

- `QuerySet.explain()` concatena string SQL (anti-padrão de segurança).
- Fingerprint de profiling não lida com aspas duplas/escaping.
- `QuerySet.count()`/`aggregate()` ignoram eager loading (inconsistência de API).
- `Seeder.save()` não refresca objeto; `Factory.create_many()` faz N inserts.
- `lookups.py` não valida tipos de valores; FK traversal limitado a um nível.
- `HeaderMarker.convert_underscores=True` pode confundir.
- WebSocket handler não fecha conexão ao negar guard; não trata exceções.
- Middleware por rota (`@route(middleware=...)`) documentado mas não aplicado.
- `BodyMarker.embed` não implementado.
- `CronScheduler` pode disparar tarefas duplicadas e não persiste `last_fired`.
- Inconsistência de idioma (PT/EN misturado) e i18n inexistente.
- `url_for` não suporta query params nem conversores tipados.
- Templates admin interpolam query strings sem `|urlencode`.
- `mypy --strict` reporta erros em produção (SAQ, imports opcionais, etc.).

---

## 6. Problemas de Baixo Risco 🟢

- Imports dentro de funções de hot path (`aura/routing/router.py`).
- `_serialize` faz `json.loads(json.dumps(...))` redundante.
- `Schema` base não inclui `extra="forbid"`.
- Health check expõe versão sem autenticação.
- Comentários `F-XX` no código.
- `_call` reinspeciona assinatura a cada resolução de DI.
- `TimingInterceptor` expõe tempo de processamento por padrão.
- `Makefile` usa `python3` (problemático no Windows).
- CI não testa Python 3.11/3.13 nem instala todos os extras opcionais.

---

## 7. Plano de Ação Prioritário

### Se houvesse 1 dia de refactoring

1. **Segurança imediata**
   - Corrigir vazamento de config em logs (`aura/core/app.py:252`).
   - Substituir `python-jose` por `pyjwt` com validação rigorosa de claims.
   - Proteger `redirect()` contra open redirect.
   - Adicionar CSRF ao admin e trocar senha plaintext por hash.
2. **Contratos quebrados**
   - Corrigir `QuerySet.last()` para respeitar `order_by()`.
   - Aplicar prefixo global `Aura(prefix=...)`.
   - Implementar `@inject` documentado ou remover da API pública.
3. **Backend SAQ**
   - Usar `saq.Queue.from_url`, corrigir unidades de `timeout`/`scheduled`.
4. **Rate limiting**
   - Tornar `RateLimitMiddleware` atômico; adicionar headers `X-RateLimit-*`/`Retry-After`.
5. **Estabilidade de testes**
   - Isolar singletons globais (`db`, container, `TaskRegistry`, admin registry) no `conftest.py`.

### Se houvesse 1 semana

- Refatorar admin para usar `AuraForm`/`ModelForm` (eliminar duplicação de parsing).
- Corrigir componentes síncronos em templates async.
- Remover auto-discovery inseguro do `env.py` de migrations.
- Implementar `ModelForm` e widgets.
- Corrigir `AuraWorker` para respeitar `queues`/`burst` e filtrar tarefas por queue.
- Adicionar guarda em `QuerySet.delete()` (`allow_unfiltered`).
- Implementar redação de dados sensíveis no `RequestLogInterceptor`.
- Zerar `mypy --strict` em produção e testes.

### Se houvesse 1 mês

- Backend de rate limit abstrato (Redis) e compartilhado.
- i18n/Babel para mensagens de erro.
- Testes de segurança (JWT manipulado, CSRF, XSS, SQL injection, open redirect).
- CI paralela com cobertura mínima (`--cov-fail-under=80`), Python 3.10–3.13 e extras opcionais.
- Documentação de limitações do ORM (agregações vs eager loading, lookups suportados).
- Refatorar `RequestPipeline` ou integrá-lo à aplicação.

---

## 8. Verificações Executadas

- `pytest tests/ -q --tb=short` → **589 passed, 2 skipped, ~12s**
- `pytest tests/ -q --cov=aura` → **80% cobertura global**
- `ruff check aura/ tests/` → 1 erro em `aura/__init__.py` (import block desordenado)
- `mypy aura/ --ignore-missing-imports` → 8 erros
- `mypy tests/ --ignore-missing-imports` → 85 erros

---

## 9. Conclusão

O Aura tem **ótima arquitetura de alto nível e uma DX promissora**, mas ainda carrega muita dívida técnica em segurança, integração de backends, contratos públicos e qualidade de testes. Os problemas críticos são corrigíveis e, uma vez resolvidos, o framework ganha muita credibilidade. A recomendação é **não usar em produção** até que os itens críticos de segurança (C1–C16) sejam endereçados.

**Relatórios detalhados por escopo:**
- `.omo/aura_analysis_architecture.md`
- `.omo/aura_analysis_orm_data.md`
- `.omo/aura_analysis_routing_security.md`
- `.omo/aura_analysis_middleware_stack.md`
- `.omo/aura_analysis_forms_templates_admin_cli.md`
- `.omo/aura_analysis_tests.md`
# CLAUDE.md — Aura Framework

> **Este arquivo é lido pelo Claude Code (o líder) no início de toda sessão.**  
> Os agentes em `.claude/agents/` são especialistas da equipe. O Claude Code principal orquestra, delega e valida.

---

## O Projeto

**Aura** é um framework Python web NestJS-inspired: async-first, type-safe, Spec-Driven.  
Resolve as dores reais do Django (ORM síncrono, sem DI real) e do FastAPI (sem estrutura, DI amarrado ao HTTP).

**PyPI:** `pip install aura-web`
**Versão:** Definida em `pyproject.toml` (fonte canônica) · `aura.__version__` lê via `importlib.metadata`
**Testes:** 673 passando · mypy strict 0 erros em `aura/` + `tests/` · ruff clean · cobertura `aura/` ≥ 75%

---

## Stack e Versões

| Componente     | Versão    | Uso                           |
| -------------- | --------- | ----------------------------- |
| Python         | 3.10+     | target mínimo                 |
| Starlette      | latest    | ASGI core                     |
| Pydantic       | v2.x      | validação em todo o framework |
| SQLAlchemy     | 2.x async | ORM                           |
| Alembic        | latest    | migrations                    |
| SAQ            | latest    | jobs async (Redis)            |
| Jinja2         | 3.x       | templates                     |
| pytest-asyncio | latest    | testes                        |

---

## Estrutura do Projeto

```
aura/
├── core/        # Aura app, request, response — zero deps de subsistemas opcionais
├── modules/     # @Module decorator, ModuleRegistry, on_startup
├── di/          # DIContainer SINGLETON/SCOPED/TRANSIENT, @injectable, inject()
├── routing/     # @get @post @put @delete @patch @ws @html @sse + param binding
├── orm/         # AuraModel, Repository[T] (+bulk, +paginate), DatabaseManager
├── guards/      # Guard base, JWTGuard, RateLimitGuard
├── middleware/  # CORS, RateLimit, Compression, SessionMiddleware
├── jobs/        # @task @periodic, MemoryBackend, SAQBackend, AuraWorker
├── templates/   # AuraTemplateEngine (Jinja2), AuraTemplateModule, url_for global
├── cli/         # aura new/run/generate/migrate/worker
└── exceptions/  # HTTPException hierarchy (400-504)

tests/           # pytest-asyncio, ASGITransport, fixtures em conftest.py
docs/
├── pending.md   # ← FONTE DA VERDADE do roadmap — ler antes de priorizar
└── decisions/   # ADRs (Architecture Decision Records)
.claude/
└── agents/      # Especialistas da equipe (ver seção abaixo)
```

---

## A Equipe — Quando Usar Cada Agente

**Você (Claude Code — líder)** orquestra, toma decisões finais, valida entregas dos subagentes, e executa tarefas simples diretamente. Não delegue o que você mesmo pode fazer em 2 minutos.

| Agente       | Ative quando...                                                                                                    | NÃO use para...             |
| ------------ | ------------------------------------------------------------------------------------------------------------------ | --------------------------- |
| `po-pm`      | "Vale a pena construir isso?", priorização, critérios de aceite, análise de roadmap                                | Qualquer código             |
| `arquiteto`  | "Como estruturar isso?", review de API pública, ADRs, identificar acoplamento                                      | Implementação de código     |
| `engenheiro` | Implementar feature aprovada, corrigir bug, escrever testes, fix lint/mypy                                         | Decisões arquiteturais      |
| `research`   | "Como outros frameworks fazem X?", verificar docs, pesquisar boas práticas                                         | Implementação               |
| `qa`         | "Isso está correto e bem feito?", auditoria de módulo, busca por bugs, código duplicado/morto, cobertura de testes | Escrever código de correção |

### Fluxo correto para uma feature nova

```
1. PO/PM → "Isso deve ser construído? Com que critérios de aceite?"
2. Arquiteto → "Como estruturar? Breaking changes? ADR necessário?"
3. Engenheiro → Implementa o contrato definido pelo Arquiteto
4. QA → Audita o que foi implementado: bugs, testes ausentes, duplicações, edge cases
5. Você (líder) → Verifica que o código realmente existe (grep), roda os testes, valida
```

---

## Princípios Inegociáveis

### 1. Leia antes de mexer

Nenhum arquivo é editado sem ser lido primeiro na sessão atual. Isso vale para você e para todos os agentes.

### 2. Verifique antes de marcar como feito

Após qualquer implementação de subagente, antes de atualizar `docs/pending.md`:

```bash
grep -n "def nome_do_metodo\|class NomeDaClasse" aura/modulo.py
python3 -m pytest tests/test_modulo.py -q --tb=no
```

Se não aparecer → **não está feito**. Independente do que o subagente relatou.

### 3. Escopo estrito

Uma sessão = uma tarefa ou um módulo. Agentes não "melhoram" código fora do escopo definido.  
Se um agente encontrar algo errado fora do escopo → **reporta, não corrige**.

### 4. API pública é contrato

Itens em `__all__` de qualquer módulo são contratos com quem usa o Aura.  
Mudanças breaking → revisão obrigatória do Arquiteto + nota no changelog.

### 5. Zero tolerância para degradação de qualidade

```bash
# Esses comandos DEVEM passar antes de qualquer commit:
python3 -m pytest tests/ -q --tb=short
python3 -m mypy aura/ --ignore-missing-imports
python3 -m mypy tests/ --ignore-missing-imports   # wave 2 — 0 erros (concluído wave 7)
python3 -m ruff check aura/ tests/
```

### 6. Extras opcionais não poluem o core

`[sqlalchemy]`, `[jwt]`, `[session]`, `[templates]` são opcionais.  
Imports deles em `aura/__init__.py` e `aura/core/` são sempre dentro de `try/except ImportError`.

---

## O Que Nenhum Agente Deve Fazer

```
❌ Adicionar dependência nova sem aprovação explícita do líder
❌ Modificar API pública (__all__) sem Architecture Gate
❌ Marcar feature como concluída sem verificar o código via grep/test
❌ Editar arquivo sem tê-lo lido nessa sessão
❌ "Melhorar" código fora do escopo da tarefa atual
❌ Usar # type: ignore como solução padrão para erros mypy
❌ Logar ou expor tokens, senhas, ou dados sensíveis
❌ Passar credenciais como argumento de linha de comando
```

---

## Protocolo de Início de Sessão (Sync Check)

Antes de qualquer implementação, o líder deve verificar o estado atual:

```
1. Leia docs/pending.md — o que está planejado?
2. Leia o arquivo do módulo em questão — qual é o estado atual?
3. Rode: python3 -m pytest tests/ -q --tb=no para confirmar baseline
4. Defina explicitamente: "Nessa sessão vamos APENAS [X]. Não toque em [Y]."
```

---

## Protocolo de Encerramento de Sessão

Ao final de cada sessão produtiva, atualize:

```
1. docs/pending.md — marque como [x] apenas o que foi VERIFICADO no código
2. CLAUDE.md — atualize versão e contagem de testes se mudaram
3. git commit com mensagem descritiva do que foi implementado
```

---

## Segurança — CRÍTICO

**Tokens PyPI do projeto `aura-web` foram expostos em sessões anteriores.**

- Revogar em: https://pypi.org/manage/account/tokens/
- Para publicar: `PYPI_TOKEN=pypi-... python3 build_to_pypi.py` (lê `.env` automaticamente)
- **Nunca** passar token como `--password` ou `--token` na linha de comando

### Hardening Waves 1–2 (2026-06)

| Área | Mudança | Breaking? |
|------|---------|-----------|
| Routing | Coerção/body inválidos → 422 | Não |
| ORM | `delete(allow_unfiltered=True)` obrigatório sem filtros | **Sim** |
| Core | `redirect()` só paths `/…`; logs de config redactam secrets | Parcial |
| JWT | Extra `[jwt]` usa **PyJWT**, não `python-jose` | **Sim** (dep) |
| Middleware | Rate limit atômico + headers; DI scope cleanup; `Aura(prefix=…)` | Não |
| SAQ | `Queue.from_url`; timeout/scheduled em segundos | Não |
| Migrations | `generate_env_py` sem `os.walk` | Parcial |
| Admin | PBKDF2, CSRF, logout POST | Não (wave 2) |

Detalhes: `docs/decisions/ADR-001-security-hardening.md` · roadmap: `docs/pending.md`

### Waves 3–8 (2026-06) — v1.4.0

| Wave | Tema | Destaques |
|------|------|-----------|
| 3 | Produção | `DatabaseMiddleware` fail-fast; `await component(...)`; SAQ `--burst` |
| 4 | DX | Redis rate limit; OpenAPI `BearerAuth`; header redaction em logs |
| 5 | Contrato | Interceptors globais; 422 estruturado; `FormDataMarker`; ADR-003 |
| 6 | Admin | `ModelForm`; CSRF em forms; ADR-004 |
| 7 | Infra | CI 3.11/3.13; pre-commit; MkDocs skeleton; fixtures autouse |
| 8 | Segurança | `trusted_proxies`; Redis Lua atômico; `require_exp` padrão; cookie sessão |

Breaking em 1.4.0: formato 422, `JWTGuard(require_exp=True)`, cookie de sessão condicional. Ver `CHANGELOG.md` e `README.md`.

---

## Comandos Úteis de Referência Rápida

```bash
# Instalar tudo para desenvolvimento
pip install -e ".[dev,sqlalchemy,jwt,session,templates]" aiosqlite

# Qualidade (deve passar antes de qualquer commit)
python3 -m pytest tests/ -q --tb=short
python3 -m mypy aura/ --ignore-missing-imports
python3 -m mypy tests/ --ignore-missing-imports
python3 -m ruff check aura/ tests/

# Publicar (use .env com PYPI_TOKEN)
python3 build_to_pypi.py

# CLI do Aura
aura new meu-projeto
aura generate module posts --with-db
aura migrate init && aura migrate make "add posts" && aura migrate up
aura worker --broker-url redis://localhost:6379
```

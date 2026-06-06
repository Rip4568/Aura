# Pontos de Melhoria — Aura Framework

> **Auditoria multi-agente** — QA, UX/Designer, e PO/PM — Jun 2026
> **Baseline:** 589 testes passando · mypy strict 0 erros · ruff clean · 80% coverage

---

## 🔴 Crítico (Corrigir Agora)

### 1. Divergência de Versão em 4 Fontes

| Fonte | Valor |
|-------|-------|
| `pyproject.toml:7` | `1.2.0` (o que o PyPI publica) |
| `aura/__init__.py:152` | `0.3.1` |
| `CLAUDE.md` + `README.md` badge | `0.4.9` |
| `docs/roadmap.md` | `v0.2.0` Alpha |

**Impacto:** Ninguém instala uma lib "1.2.0" cujo README diz ser Alpha. Desenvolvedores confundem se o projeto está maduro ou não. O `__init__.py` ficou 4 versões atrás do `pyproject.toml`.

**Solução:** Unificar em `0.5.0` e estabelecer processo de bump automático (ver `docs/version-unification.md`).

### 2. Admin: Senha em Plaintext sem Hash (`views.py:142`)

```python
# aura/admin/views.py:142
if submitted == password:  # Comparação direta, sem hash!
```

Nenhum hashing (bcrypt/argon2), sem proteção contra brute-force. Se um atacante acessar o `.env` (ou a env var vazar), a senha admin está exposta.

### 3. Admin: Sem Proteção CSRF nos Formulários

- `login.html:61` — formulário de login sem token CSRF
- `form.html:28` — todos os forms de CRUD sem token CSRF

A autenticação usa cookies de sessão (`SessionMiddleware`), que são vulneráveis a CSRF sem proteção.

### 4. Admin Exposto sem Senha em Dev (`views.py:87`)

```python
# aura/admin/views.py:87
is_debug = os.getenv("AURA__DEBUG", "true").lower() in ("true", "1")
if not is_debug:
    raise RuntimeError("AURA_ADMIN_PASSWORD must be configured in production...")
return None  # Senha ignorada se debug=true (padrão!)
```

O padrão de `AURA__DEBUG` é `"true"` quando não setado. Combinado com `AURA_ADMIN_PASSWORD` não definido, o admin fica completamente aberto.

### 5. Token PyPI Exposto em Sessão Anterior

O token de publicação do PyPI foi exposto em log de sessão. **Revogar imediatamente** em https://pypi.org/manage/account/tokens/ e gerar novo.

### 6. `except Exception: pass` Silencioso — 16+ Instâncias

| Arquivo | Linhas | Impacto |
|---------|--------|---------|
| `cli/commands/tinker.py` | 85-86, 152-153, 163-164, 170-171 | Erros de import/config/DB silenciados |
| `cli/commands/seed.py` | 63-64, 72-73, 148-149, 159-160, 166-167 | Idem — código quase duplicado |
| `core/app.py` | 253-255, 264-265 | `on_startup`/`on_shutdown` falham silenciosamente |
| `routing/router.py` | 991, 1004 | Mounts e OpenAPI falham sem log |
| `orm/session.py` | 70 | Erro de DB swallowing |

**Padrão a adotar:**
```python
except ImportError:
    pass  # Opcional não instalado — ok
except Exception as e:
    logger.exception("Falha ao inicializar X: %s", e)  # Logar, não engolir
```

### 7. `orm/__init__.py:81` — Reset Frágil de `__all__`

```python
except ImportError:
    __all__ = []   # Line 81 — reseta completamente
```

Se SQLAlchemy não está instalado, `__all__` vira `[]` na linha 81. Depois, na linha 95, `__all__ += [...]` tenta adicionar profiling symbols. Se profiling importar sem SQLAlchemy, a lista fica inconsistente.

---

## 🟠 Alta Prioridade

### 8. Sem Páginas de Erro HTML para Rotas `@html`

**`aura/exceptions/handlers.py:34-50`** — O `exception_handler` sempre retorna `JSONResponse`. Rotas `@html` que lançam exceções mostram JSON cru no navegador em vez de uma página de erro amigável.

### 9. Docs Website Inexistente — Bloqueador de Adoção #1

O README tem 1127 linhas, mas não substitui documentação. Falta:
- API Reference (todos os decorators, classes, parâmetros)
- Tutorial passo a passo ("Building a Blog with Aura")
- Deployment guide (Docker, Granian, Gunicorn)
- Migration guides (Django → Aura, FastAPI → Aura)

**Solução:** MkDocs Material + GitHub Pages. Prioridade máxima para adoção.

### 10. Sem Benchmarks Publicados

`motivation.md` cita DRF sendo 377x mais lento que Python puro, mas o Aura não tem um único benchmark próprio. "Trust me, it's fast" não convence ninguém.

### 11. Sem `AuraTestCase` ou Helper `mock_service()`

Testes com DI requerem boilerplate manual para criar container, registrar mocks, e obter `AsyncClient`. Sem classe base, cada projeto reinventa a roda.

### 12. Geração de Scaffold com Segredo Hardcoded (`new.py:53`)

```python
# aura/cli/commands/new.py:53 — scaffold do main.py
SessionMiddleware(secret_key="change-me-in-production-32chars!!")
```

Todo projeto novo gerado pelo `aura new` commita esse segredo fixo no git. Deveria usar `secrets.token_urlsafe(32)` como já faz para `.env`.

### 13. Admin: Duplicação Massiva de Código (`views.py`)

O mapeamento coluna→campo (`column_type → field_type`) é repetido 4x (~160 linhas duplicadas) em `create_form`, `create_record`, `edit_form`, `edit_record`. Extrair para método `_build_form_fields(model)` eliminaria ~120 linhas.

### 14. Módulos com Cobertura Abaixo de 50%

| Módulo | Cobertura | Linhas Perdidas |
|--------|-----------|----------------|
| `core/pipeline.py` | 33% | 32/48 |
| `templates/module.py` | 21% | 22/28 |
| `middleware/compression.py` | 30% | 14/20 |
| `jobs/backends/saq_backend.py` | 39% | 25/41 |
| `templates/component.py` | 54% | 16/35 |

### 15. Admin: `hover:bg-slate-850` Não Existe no Tailwind

`layout.html:52,61` usa `hover:bg-slate-850` — cor que não existe na paleta padrão do Tailwind (vai de 800 a 900). O hover visual simplesmente não funciona. Deveria ser `hover:bg-slate-800`.

### 16. `QueryCountMiddleware` Listado no README mas sem Documentação Separada

O middleware existe e funciona, mas não tem doc próprio em `docs/`. A seção do README é boa, mas não é indexável/descobrível.

---

## 🟡 Média Prioridade

### 17. Admin: Zero Atributos ARIA
Nenhum template admin tem `role`, `aria-label`, `scope="col"`, ou link skip-to-content. Inacessível para leitores de tela.

### 18. Admin: `per_page` Hardcoded em 10 (`views.py:241`)
O `ModelAdmin` base define `per_page = 25`, mas `views.py:241` ignora e usa `10` hardcoded.

### 19. Admin: `<html lang>` Inconsistente
- `layout.html:2`: `lang="en"`
- `login.html:2`: `lang="pt-BR"`

### 20. CLI: `aura run` sem Validação de `app_path`
Se o módulo não existe, o uvicorn crasha com erro críptico.

### 21. CLI: `aura version` Cai para `"0.1.0"` Silenciosamente
```python
try:
    from aura import __version__
except ImportError:
    __version__ = "0.1.0"  # Fallback silencioso
```

### 22. OpenAPI: Sem `securitySchemes` para JWTGuard
Apesar do framework ter `JWTGuard`, o OpenAPI gerado não inclui `securitySchemes`.

### 23. Swagger/ReDoc Dependem de CDN
Swagger UI via `unpkg.com`, ReDoc via Google Fonts CDN. Sem opção offline.

### 24. Admin: Navegação Reconstrói `models_nav` a Cada Request
`render_admin()` (`views.py:27-55`) monta a lista de modelos a cada chamada.

### 25. Admin: Paginação com Concatenação de String (`table_body.html:66`)
URLs de paginação concatenam filtros manualmente. Valores com `&` ou `=` quebram a navegação.

### 26. Duplicação: `tinker.py` + `seed.py` — Config Discovery
Ambos têm código quase idêntico (~50 linhas cada) para descobrir módulos, carregar `aura.toml` e inicializar `db.init()`.

### 27. Admin: Delete usa `hx-confirm` Nativo
O diálogo de confirmação de delete é o `window.confirm()` nativo do navegador (sem estilo).

### 28. `aura/forms/__init__.py:98-109`: Imports para Arquivos Inexistentes
```python
try:
    from aura.forms.modelform import ModelForm  # Arquivo não existe
except ImportError:
    pass
```
Os comentários dizem "v0.6.1 extras — not yet implemented".

### 29. Swagger sem Customização de Marca
Tema padrão sem logo, favicon, ou CSS customizado.

---

## 🟢 Baixa Prioridade

### 30. Admin: Sem `<meta name="theme-color">`
Falta meta tag para colorir a status bar em PWA/mobile.

### 31. Admin: `htmx-boost="true"` no `<body>`
Todas as âncoras viram AJAX — pode quebrar links para fora do admin.

### 32. Admin: Sem `<caption>` nas Tabelas
`table_body.html` não tem `<caption>` — requisito básico de acessibilidade.

### 33. Admin: Botão Cancelar é `<a>` em vez de `<button>`
`form.html:106` usa um link para "Cancelar", quebrando navegação por teclado.

### 34. CLI: Sem Flag `--json` nos Comandos
Nenhum comando suporta saída JSON para consumo por scripts/CI.

### 35. `aura/cli/__init__.py` — Sem `__all__`
Apenas docstring, sem exports explícitos.

### 36. `aura/templates/tags/__init__.py` — Placeholder Vazio
Apenas um comentário, sem código.

### 37. README: Badge de Testes Desatualizado
Mostra "347 tests passing" mas o projeto tem **589**.

### 38. `_plural()` Não Lida com Plurais Irregulares
`aura/cli/commands/generate.py:28-30` — `"sheep"` → `"sheeps"`, `"child"` → `"childs"`.

### 39. `assert isinstance` em Código de Produção
`aura/cli/commands/generate.py:382` — se falhar, não há mensagem de erro útil.

### 40. Admin: Sem i18n
Todas as strings hardcoded em inglês (ou mistura pt-BR/en).

### 41. Admin: Footer com Versão Hardcoded
`layout.html:70`: `"Aura Framework v0.3.1"` — vai divergir da versão real a cada release.

---

## 🧭 Prioridades do Roadmap (Visão PO/PM)

### O Que Deveria Subir de Prioridade

| Item | Prioridade Atual | Sugerida | Justificativa |
|------|-----------------|----------|---------------|
| Docs website (MkDocs) | Baixa | **Altíssima** | Bloqueador de adoção #1 |
| Exemplos completos | Baixa | **Alta** | Principal onboarding |
| Benchmarks | Baixa | **Alta** | Crítico para credibilidade |
| `AuraTestCase` + `mock_service` | Baixa | **Alta** | Bloqueador de produção |
| `CHANGELOG.md` | PyPI (Baixa) | **Alta** | Básico para qualquer projeto |

### O Que Deveria Descer / Cortar do Curto Prazo

| Item | Justificativa |
|------|---------------|
| Islands Architecture | Nicho, complexidade alta, adia v1.0 |
| gRPC Controller | Público minúsculo para Python web |
| Multi-tenancy | Só relevante para SaaS enterprise |
| `msgspec` | Otimização prematura sem benchmarks |

### Escopo Recomendado para v1.0

```
v1.0.0 — "Production Ready"
├── Core (routing, DI, guards, interceptors)          ✅ Estável
├── ORM (Repository, paginate, migrations)             ✅ Estável
├── Jobs (SAQ backend, periodic tasks)                 ✅ Estável
├── Admin Panel                                        ✅ Funcional (melhorar CSRF/senha)
├── Logging (AuraLogSystem v1.0)                       ✅ Estável
├── WebSocket Gateway (@Gateway + rooms)               🚧 Em progresso
├── OpenTelemetry básico (traces)                      📋 Pendente
├── AuraTestCase + mock_service                        📋 Pendente
├── Docs website (MkDocs + GitHub Pages)               📋 Pendente
├── 3 exemplos completos (todo, blog, ecommerce)       📋 Pendente
├── Benchmarks publicados                              📋 Pendente
├── CHANGELOG.md (Keep a Changelog)                    📋 Pendente
├── Plugin system mínimo                               📋 Pendente
├── Versão unificada                                   📋 Pendente
└── Segurança admin (CSRF + hash senha)                🔴 Pendente
```

---

## 📊 Resumo Estatístico

| Categoria | Count |
|-----------|-------|
| 🔴 Crítico | 7 |
| 🟠 Alta Prioridade | 9 |
| 🟡 Média Prioridade | 13 |
| 🟢 Baixa Prioridade | 12 |
| **Total** | **41** |

| Métrica | Valor |
|---------|-------|
| Testes passando | 589 |
| Cobertura | 80% |
| Módulos <50% cobertura | 5 |
| `# type: ignore` | 16 |
| `except Exception: pass` | 16+ |
| `__all__` ausente | 3 módulos |
| Dead imports | 2 (`ModelForm`, `Widget`) |
| Versões divergentes | 4 fontes |
| Código duplicado | 2 blocos (~100 linhas cada) |

---

## 🎯 Top 5 Ações de Maior Impacto/Esforço

| # | Ação | Impacto | Esforço |
|---|------|---------|---------|
| 1 | Unificar versão (0.5.0) em todas as fontes | Crítico | 15 min |
| 2 | Adicionar CSRF token nos forms do admin | Crítico | 2-3h |
| 3 | Hash bcrypt na senha admin + rate-limit | Crítico | 2-3h |
| 4 | Páginas de erro HTML para rotas `@html` | Alto | 3-4h |
| 5 | Substituir `except Exception: pass` por logging | Médio | 4-6h |

---

## 📅 Plano de Ação (Sugestão)

### Semana 1 — Segurança + Versão
- [ ] Revogar token PyPI exposto
- [ ] Unificar versão em 0.5.0
- [ ] CSRF protection nos forms admin
- [ ] Hash de senha admin
- [ ] Corrigir `AURA__DEBUG` default inseguro
- [ ] Substituir segredo hardcoded no scaffold por `secrets.token_urlsafe()`

### Semana 2 — Qualidade de Código
- [ ] Substituir `except Exception: pass` por logging adequado
- [ ] Extrair código duplicado tinker/seed para `cli/utils.py`
- [ ] Remover dead imports `ModelForm`/`Widget` ou criar stubs
- [ ] Adicionar `__all__` nos módulos faltantes

### Semana 3-4 — UX + Docs
- [ ] Páginas de erro HTML para rotas `@html`
- [ ] Corrigir `hover:bg-slate-850` → `hover:bg-slate-800`
- [ ] Adicionar atributos ARIA nos templates admin
- [ ] Corrigir `per_page` para respeitar `ModelAdmin.per_page`
- [ ] Criar `CHANGELOG.md`
- [ ] Atualizar badge de testes no README

### Mês 2 — Adoção & Ecossistema
- [ ] Docs website com MkDocs Material
- [ ] Tutorial "Building a Blog with Aura"
- [ ] 3 exemplos completos
- [ ] Benchmarks vs FastAPI / Django
- [ ] `AuraTestCase` + `mock_service()`

### Mês 3 — v1.0
- [ ] WebSocket Gateway
- [ ] OpenTelemetry básico
- [ ] Plugin system mínimo
- [ ] Publicar v1.0.0

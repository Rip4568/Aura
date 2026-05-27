# Pesquisa: Sistemas de Templates Modernos em Python

> Relatório gerado por subagente de pesquisa — base para design do `aura.templates`

## Problemas Fundamentais dos Frameworks Atuais

### Django Templates
- **Sem type-safety**: contexto é `dict` livre — erros só aparecem em produção
- **N+1 em templates**: `{{ post.author.name }}` dentro de loop dispara N queries (lazy-load ORM)
- **Template tags verbosas**: `{% if %}`, `{% for %}`, `{% load %}` — lógica misturada com HTML
- **Context processors globais**: injetam dados silenciosamente, sem contrato declarado
- **Sem sistema de componentes**: `{% include %}` passa o contexto inteiro, sem validação

### Flask/Jinja2
- Herda todos os problemas do Django Templates
- Macros (`{% macro %}`) não são componentes: sem validação, sem documentação, difíceis de testar
- FastAPI usa Jinja2 mas sem integração real de type-safety

### Django REST Framework (DRF)
- Serializers não são Pydantic: sem type-checking nativo
- N+1 em serialização sem `select_related`/`prefetch_related`
- `TemplateHTMLRenderer` raramente usado e frágil

### Django-Ninja
- Resolveu a API JSON (Pydantic + async) mas ignorou renderização HTML
- Sem componentes reutilizáveis, sem integração HTMX

---

## Abordagens Modernas (benchmarks para o Aura)

### HTMX — HTML-over-the-wire
- Servidor retorna **fragmentos HTML**, não JSON
- Cliente atualiza partes da página via atributos HTML
- **14 KB** gzipped vs 200+ KB de um SPA
- SEO nativo, sem hydration, debugging simples
- Stack: Backend Python + HTMX = sem JS framework complexo

### Alpine.js — interatividade local leve
- **7 KB** — para estado local (modais, dropdowns, tabs)
- Complementa HTMX: HTMX para server, Alpine para client local state
- Sem build, sem compilação

### Islands Architecture (Astro)
- HTML estático + ilhas JS interativas seletivas
- Zero JS por padrão, hidrata apenas o necessário
- Melhor performance: TTI muito mais baixo que SPA

### Templ (Go) — lição de type-safety
- Templates Go **compilados** — erros de tipo em build time
- Composição type-safe: `@UserCard(user)` com tipos verificados
- Python poderia imitar: Pydantic como spec do contexto

### Phoenix LiveView (Elixir)
- State management server-side via WebSocket
- Servidor envia **diffs** do DOM, não re-render completo
- Inspiração para futura feature de Aura

### Hotwire/Turbo (Rails)
- Turbo Frames: substitui seções da página (como HTMX)
- Turbo Streams: broadcast real-time de HTML fragments

---

## Stack Recomendado para 2025-2026

| Camada | Escolha | Razão |
|---|---|---|
| Renderização | Jinja2 (server-side) | Familiar, extensível, rápido |
| Contexto | Pydantic `TemplateContext` | Type-safe, validado, spec-driven |
| Componentes | Classes Python + Jinja2 | Testáveis, reutilizáveis |
| Interatividade | HTMX | Server-first, sem SPA |
| Estado local | Alpine.js | Leve, sem build |
| Real-time | WebSocket / SSE | Nativo em ASGI |
| N+1 prevention | Context em Python (prefetch) | Nunca queries em templates |

---

## Princípios para o Aura Templates

1. **Context é Pydantic** — validado antes de renderizar, nunca `dict` livre
2. **Componentes são Python** — classes tipadas, testáveis em isolamento
3. **HTMX first-class** — `request.htmx` detecta, `response.htmx` controla
4. **Sem N+1** — contexto construído em Python com eager loading
5. **Progressive enhancement** — HTML funciona sem JS
6. **Islands** — ilhas JS seletivas em HTML estático
7. **Hot reload** — templates recarregam em dev sem restart

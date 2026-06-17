# ADR-002: Templates Async-Only (C15)

**Status:** Proposto para Wave 3  
**Data:** 2026-06-17  
**Autores:** Arquiteto · Engenheiro  
**Afeta:** `aura/templates/engine.py` · Templates em produção

---

## Contexto

Atualmente, `AuraTemplateEngine` registra um componente global síncrono (`_render_component_sync`) que internamente chama `asyncio.run_until_complete()` para executar componentes async dentro de templates.

```python
# Current (broken pattern)
def _render_component_sync(self, name: str, **kwargs: Any) -> str:
    """Sync wrapper used from Jinja2 globals (Jinja2 calls these synchronously
    but the env runs in async mode, so the coroutine is scheduled inline).
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    return loop.run_until_complete(self.render_component(name, **kwargs))
```

Este padrão é **perigoso em produção**:

1. **Deadlock risk**: Se a loop de eventos já está rodando, `run_until_complete()` bloqueia a loop
2. **Async context violation**: Viola a semântica assíncrona do Jinja2 em modo async
3. **Debugging nightmare**: Erros async internos à `render_component()` são mascarados
4. **Threading issues**: Pode falhar em workers multi-thread ou executores async

### Research

Jinja2 em modo async (`enable_async=True`) **já suporta natively** `await` dentro de templates:

```jinja2
{# Funciona nativamente #}
{{ await component('my_button', label='Click me') }}
```

Não há razão para wrapper síncrono.

---

## Decisão

**Remover `_render_component_sync()` inteiramente.**

Forçar todos os componentes a serem renderizados via `await component(...)` dentro de templates async.

---

## Justificativa

### Por que remover?

1. **Async-correctness**: Elimina antipadrão `run_until_complete()`
2. **Segurança**: Sem risco de deadlock em produção
3. **Simpleza**: -30 linhas de código frágil
4. **Manutenibilidade**: Menos casos especiais, melhor error propagation
5. **Performance**: Sem overhead de criar/fechar loops dinâmicos

### Por que NÃO manter por compatibilidade?

- Risco: Usuários que ignoraram a deprecation warning usarão antipadrão
- Debt: Cada nova feature de templates precisa considerar o caminho sync
- Tempo: Manutenção de ambos os paths custariam mais que migração de usuários

### Trade-offs aceitos

- **Breaking change**: Templates que usam `component(...)` sem `await` vão quebrar
  - **Mitigação**: 
    - Anúncio claro em CHANGELOG
    - Erro legível (Jinja2 dirá que `component` retorna coroutine)
    - Exemplo de migração na docs
- **Sem backward-compat**: Usuarios precisam atualizar templates
  - **Mitigação**: Pattern é simples (`add await` antes de `component`)

---

## Solução

### Mudanças de Código

**aura/templates/engine.py** (lines 76–78):
```python
# Antes
self._env.globals.update({
    "component": self._render_component_sync,
    "static": self._static_url,
})

# Depois
self._env.globals.update({
    "component": self.render_component,  # async!
    "static": self._static_url,
})
```

**Remover** linhas 180–189 (`_render_component_sync` method).

### Documentação

**aura/templates/engine.py** (docstring em `AuraTemplateEngine.__init__`):
```python
        - ``component(name, **kwargs)`` — render a registered component.
          Must be used with `await` in async templates: `{{ await component(...) }}`
```

### Exemplos

**Antes:**
```jinja2
<!-- Old pattern (will break) -->
<div>{{ component('button', label='Click') }}</div>
```

**Depois:**
```jinja2
<!-- New pattern (required) -->
<div>{{ await component('button', label='Click') }}</div>
```

### Testes

Qualquer teste que chama `component(...)` sem `await` em template deve ser atualizado.

---

## Consequências

### Imediatas

- ✅ Código mais simples (sem `_render_component_sync`)
- ✅ Async semantic correctness
- ✅ Sem deadlock risk

### Migration Path

| Versão | Ação |
|--------|------|
| 1.2.0  | Deprecation warning adicionado (optional) |
| 1.3.0  | **C15 Wave 3** — `_render_component_sync` removido |
| 2.0.0  | (futuro) Cleanup da codebase de template |

### Para Usuários

**Template que quebra:**
```jinja2
{{ component('card', title='Hello') }}
```

**Erro esperado:**
```
jinja2.exceptions.TemplateRuntimeError: component() requires 'await'
```

**Migração (1 linha mudança):**
```jinja2
{{ await component('card', title='Hello') }}
```

---

## Alternativas Consideradas

### ❌ Alternativa A: Manter sync wrapper (descartada)

**Por que não:**
- Propaga antipadrão `run_until_complete()`
- Custo de manutenção contínuo
- Não resolve problema de deadlock (só o esconde)

### ❌ Alternativa B: Usar Task/Future wrapper (descartada)

**Por que não:**
- Ainda requer escalonamento manual
- Mais complexo que remover
- Jinja2 async já resolve nativamente

### ✅ Alternativa C: Remover (ESCOLHIDA)

**Por que:**
- Simples
- Jinja2 async suporta nativamente
- Força melhores práticas

---

## Implementação Wave 3

**Task:** `C15 — Remover Componentes Síncronos em Templates`

**Checklist:**
- [ ] Remover `_render_component_sync()` (linhas 180–189)
- [ ] Atualizar globals (linha 78)
- [ ] Atualizar docstring
- [ ] Criar ADR-002 (este documento)
- [ ] Atualizar CHANGELOG: "C15: Remove async antipattern in templates"
- [ ] Atualizar exemplos em docs/
- [ ] Adicionar tipo de migração em README ou migração guide
- [ ] Rodar `pytest tests/test_templates.py` — atualizar testes que usam `component()` sem `await`

---

## Exemplos de Migração

### Exemplo 1: Simple Component

```diff
- {{ component('button', label='Submit') }}
+ {{ await component('button', label='Submit') }}
```

### Exemplo 2: Loop

```diff
- {% for btn in buttons %}
-   {{ component('button', label=btn) }}
- {% endfor %}
+ {% for btn in buttons %}
+   {{ await component('button', label=btn) }}
+ {% endfor %}
```

### Exemplo 3: Conditional

```diff
- {% if show_modal %}
-   {{ component('modal', title='Confirm') }}
- {% endif %}
+ {% if show_modal %}
+   {{ await component('modal', title='Confirm') }}
+ {% endif %}
```

---

## Perguntas Frequentes

**P: Por que não avisar os usuários antecipadamente?**  
R: Vamos avisar via CHANGELOG e GitHub issue (breaking change). Padrão é simples o suficiente que documentação é suficiente.

**P: E se template for renderizado fora de async context?**  
R: Já seria erro com Jinja2 async. Usuários devem renderizar via `await engine.render()`, não `engine.render()`.

**P: Como fazer debug se component async falha?**  
R: Stack trace agora será legível (sem `run_until_complete` mascarando a coroutine).

---

## Aprovação

- [ ] Arquiteto: Verificou integridade arquitetural
- [ ] Engenheiro: Implementou C15
- [ ] QA: Auditor de código
- [ ] Líder: Verificou via grep+pytest

---

**Documento:** `docs/decisions/ADR-002-async-templates-only.md`  
**Link Wave 3:** `docs/WAVE3_IMPLEMENTATION_PLAN.md` (Task 2: C15)

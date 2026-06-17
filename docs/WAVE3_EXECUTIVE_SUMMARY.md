# Wave 3 — Resumo Executivo

**Data:** 2026-06-17  
**Versão Alvo:** 1.3.0  
**Branch:** `fix/wave3-production-stability`  
**Status:** Plano arquitetural (pronto para engenheiros)

---

## Quick Reference — 7 Tarefas Críticas

| # | ID | Tarefa | Arquivo | Complexidade | Tempo | Breaking? | Fase |
|----|----|----|------|----|----|----|----|
| 1 | C12 | Fail-fast BD init | `aura/orm/middleware.py` | Média | 45m | Não | 1 |
| 2 | C15 | Remover sync em templates | `aura/templates/engine.py` | Alta | 1h30m | **Sim** | 1 |
| 3 | C3 | Guard + LRU + headers | `aura/guards/rate_limit.py` | Média | 1h | Não | 1 |
| 4 | A7 | Worker queues/burst SAQ | `aura/jobs/worker.py` | Baixa | 30m | Não | 1 |
| 5 | A8 | TaskRegistry isolamento | `aura/jobs/base.py` | Baixa | 30m | Não | 1 |
| 6 | mypy | 8 erros aura/ | Múltiplos | Variável | 1-2h | Não | 2 |
| 7 | test_tinker | 2 falhas | `tests/test_tinker.py` | Média | 45m | Não | 3 |

---

## Por Tarefa — O Que Fazer

### **1️⃣ C12 — DatabaseMiddleware Fail-Fast**

**Problema:** Lazy init falha silenciosamente → requests prosseguem sem BD  
**Solução:** Retornar HTTP 500 se init falha + flag `_lazy_init_failed`  
**Verificação:**
```bash
grep -n "_lazy_init_failed" aura/orm/middleware.py
pytest tests/test_orm.py tests/test_middleware.py -q
```

---

### **2️⃣ C15 — Remover Componentes Síncronos em Templates**

**Problema:** `_render_component_sync()` usa `run_until_complete()` → deadlock risk  
**Solução:** Remover função, forçar `await component(...)` em templates  
**Breaking:** Sim (documentar em CHANGELOG + ADR-002)  
**Verificação:**
```bash
grep "_render_component_sync" aura/templates/engine.py  # deve estar vazio
pytest tests/test_templates.py -q
```

---

### **3️⃣ C3 — RateLimitGuard Alinhar com Middleware**

**Problema:** Guard sem headers 429, memória sem limite  
**Solução:** Adicionar `max_tracked_keys` (LRU), headers X-RateLimit-* + Retry-After  
**Verificação:**
```bash
grep -n "max_tracked_keys\|X-RateLimit" aura/guards/rate_limit.py
pytest tests/test_guards_auth.py -k rate_limit -q
```

---

### **4️⃣ A7 — AuraWorker Respeitar Queues/Burst em SAQ**

**Problema:** CLI flags `--queue` / `--burst` ignoradas → worker não usa  
**Solução:** Passar `queues` e `burst` a `SAQWorker.__init__()`  
**Verificação:**
```bash
grep "SAQWorker(" aura/jobs/worker.py | grep -E "queues|burst"
pytest tests/test_jobs_worker.py -q
```

---

### **5️⃣ A8 — TaskRegistry Isolamento Entre Testes**

**Problema:** Singleton global sem limpeza → test pollution  
**Solução:** Adicionar `clear()` method + fixture autouse em conftest  
**Verificação:**
```bash
grep "def clear" aura/jobs/base.py
grep "reset_task_registry" tests/conftest.py
pytest tests/ -q
```

---

### **6️⃣ mypy aura/ — 8 Erros Residuais**

**Problema:** Type hints incompletos em jwt.py, admin/views.py, core/app.py, tinker.py  
**Solução:** Adicionar type annotations explícitas, imports em `TYPE_CHECKING`  
**Verificação:**
```bash
python -m mypy aura/ --ignore-missing-imports
# Deve retornar: Success: 0 errors in X source files
```

---

### **7️⃣ test_tinker.py — 2 Falhas**

**Problema:** 2 testes falhando (diagnóstico necessário)  
**Solução:** Corrigir fixtures ou mocks conforme erro específico  
**Verificação:**
```bash
pytest tests/test_tinker.py -v --tb=short  # Deve passar
```

---

## Mapa de Paralelização

```
FASE 1 (Paralelo: Tasks 1, 2, 3, 4, 5)
├─ 45 min: C12 (BD middleware)
├─ 1h30m: C15 (Templates) — ATUALIZAR testes em paralelo
├─ 1h: C3 (Rate limit guard + LRU)
├─ 30m: A7 (Worker SAQ)
└─ 30m: A8 (TaskRegistry)

FASE 2 (Sequencial: Task 6)
└─ 1-2h: mypy aura/ (após todas acima)

FASE 3 (Sequencial: Task 7)
└─ 45m: test_tinker.py (após estado limpo)

Total: 2.5–3.5h (paralelo) | 5–6h (sequencial)
```

---

## ADRs Necessários

### ADR-002: Templates Async-Only (C15)

- **Contexto:** Component render usa `run_until_complete()` — perigoso em async
- **Decisão:** Remover `_render_component_sync()`, forçar `await`
- **Justificativa:** Async-correctness, sem deadlock, simples
- **Breaking:** Sim (templates com `component(...)` sem `await` quebram)

---

## Checklist Pré-Implementação

### Engenheiro Deve

- [ ] Ler `docs/WAVE3_IMPLEMENTATION_PLAN.md` completo
- [ ] Criar branch `fix/wave3-production-stability` de `main`
- [ ] Escolher estratégia: paralelo ou sequencial
- [ ] Para **Task 3 (C3)**: verificar `HTTPException` se suporta `headers`
- [ ] Para **Task 4 (A7)**: verificar `SAQWorker.__init__()` signature em SAQ docs
- [ ] Para **Task 6 (mypy)**: rodar `mypy aura/ --ignore-missing-imports --show-error-codes` antes de começar
- [ ] Para **Task 7 (test_tinker)**: rodar `pytest tests/test_tinker.py -v --tb=long` para diagnóstico

### Verificação Pós-Implementação

```bash
# Tudo deve passar antes de considerar Wave 3 completa

pytest tests/ -q --tb=short
# → 607+ testes passando

python -m mypy aura/ --ignore-missing-imports
# → Success: 0 errors

python -m ruff check aura/ tests/
# → 0 issues

# Específicas por task
grep -c "_lazy_init_failed" aura/orm/middleware.py  # > 0
grep "_render_component_sync" aura/templates/engine.py  # vazio
grep -c "max_tracked_keys" aura/guards/rate_limit.py  # > 0
grep -c "X-RateLimit" aura/guards/rate_limit.py  # > 0
grep -c "queues.*burst" aura/jobs/worker.py  # > 0
grep -c "def clear" aura/jobs/base.py  # > 0
grep -c "reset_task_registry" tests/conftest.py  # > 0
```

---

## Notas Importantes

1. **C15 é breaking**: Atualizar CHANGELOG, documentar migração
2. **ADR-002**: Criar antes de mergear C15
3. **Task 6**: Mypy é global — executar após todas tarefas
4. **Task 7**: Requer estado limpo — executar por último
5. **Padrão Wave**: Sem código = plano testável + verificável

---

## Próximos Passos

1. ✅ **Arquiteto** cria plano (FEITO)
2. ⏳ **Engenheiro** implementa (começar aqui)
3. ⏳ **QA** audita (após implementação)
4. ⏳ **Líder** verifica (grep + pytest antes de merge)

---

**Documento gerado:** `docs/WAVE3_IMPLEMENTATION_PLAN.md`  
**Branch recomendado:** `fix/wave3-production-stability`  
**Contato para dúvidas:** Veja Arquiteto no protocolo CLAUDE.md

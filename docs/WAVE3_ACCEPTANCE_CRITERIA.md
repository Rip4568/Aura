# Wave 3 — Critérios de Aceite Verificáveis (grep + pytest)

**Objetivo:** Listar exatamente o que será testado após implementação de cada tarefa.

---

## Task 1: C12 — DatabaseMiddleware Fail-Fast

### Critérios de Aceite

#### 1. Flag `_lazy_init_failed` existe
```bash
grep -n "_lazy_init_failed" aura/orm/middleware.py
```
✅ Deve retornar pelo menos 2 ocorrências (decl + uso)

#### 2. Inicialização em __init__
```bash
grep -n "def __init__" -A 5 aura/orm/middleware.py | grep "_lazy_init_failed"
```
✅ Deve ter `self._lazy_init_failed = False`

#### 3. Flag setado em _try_lazy_init
```bash
grep -n "_try_lazy_init" -A 20 aura/orm/middleware.py | grep "_lazy_init_failed"
```
✅ Deve ter `self._lazy_init_failed = True` em bloco except

#### 4. Retorna 500 quando flag está True
```bash
grep -n "if.*_lazy_init_failed" aura/orm/middleware.py
```
✅ Deve ter condicional que checa flag

#### 5. Response 500 é enviada
```bash
grep -n "500\|Service Unavailable" aura/orm/middleware.py
```
✅ Deve ter mensagem 500 ou "Service Unavailable"

#### 6. Testes ORM passam
```bash
pytest tests/test_orm.py -q --tb=short
pytest tests/test_middleware.py -q --tb=short
```
✅ Todos testes passam

---

## Task 2: C15 — Remover Componentes Síncronos

### Critérios de Aceite

#### 1. `_render_component_sync` foi removido
```bash
grep "_render_component_sync" aura/templates/engine.py
```
✅ Deve retornar VAZIO (sem resultado)

#### 2. `component` global aponta para `render_component`
```bash
grep -n "self._env.globals\[" aura/templates/engine.py | grep component
```
✅ Deve ter `"component": self.render_component` (não sync)

#### 3. ADR-002 existe
```bash
test -f docs/decisions/ADR-002*.md && echo "OK" || echo "FAIL"
```
✅ Deve existir ADR-002 em `docs/decisions/`

#### 4. ADR-002 menciona templates async
```bash
grep -i "async" docs/decisions/ADR-002*.md | grep -i template
```
✅ Deve mencionar "async templates" e "remover sync"

#### 5. Testes de templates passam
```bash
pytest tests/test_templates.py -q --tb=short
```
✅ Todos testes passam

#### 6. CHANGELOG atualizado
```bash
grep -i "C15\|components\|templates\|async" CHANGELOG.md | head -5
```
✅ Deve mencionar breaking change

---

## Task 3: C3 — RateLimitGuard com LRU + Headers

### Critérios de Aceite

#### 1. `max_tracked_keys` parâmetro existe
```bash
grep -n "max_tracked_keys" aura/guards/rate_limit.py
```
✅ Deve ter `max_tracked_keys` em `__init__` signature

#### 2. `_key_order` list existe
```bash
grep -n "_key_order" aura/guards/rate_limit.py
```
✅ Deve ter `self._key_order = []` em `__init__`

#### 3. `_cleanup_oldest_key` method existe
```bash
grep -n "def _cleanup_oldest_key" aura/guards/rate_limit.py
```
✅ Deve existir método

#### 4. Cleanup é chamado em `can_activate`
```bash
grep -n "can_activate" -A 10 aura/guards/rate_limit.py | grep "_cleanup_oldest_key"
```
✅ Deve chamar cleanup se `len(self._requests) > self.max_tracked_keys`

#### 5. Headers X-RateLimit em resposta 429
```bash
grep -n "X-RateLimit" aura/guards/rate_limit.py
```
✅ Deve ter pelo menos 2 ocorrências (limit + remaining)

#### 6. Retry-After header
```bash
grep -n "Retry-After" aura/guards/rate_limit.py
```
✅ Deve ter `Retry-After` header

#### 7. HTTPException suporta headers (verificação)
```bash
grep -n "class HTTPException" aura/exceptions/http.py
grep -n "headers" aura/exceptions/http.py
```
✅ `HTTPException` deve ter parâmetro `headers`

#### 8. Testes rate limit passam
```bash
pytest tests/test_guards_auth.py -q --tb=short -k "rate"
```
✅ Todos testes passam

---

## Task 4: A7 — AuraWorker Queues/Burst SAQ

### Critérios de Aceite

#### 1. `_run_saq_worker` passa `queues`
```bash
grep -n "SAQWorker(" -A 3 aura/jobs/worker.py | grep queues
```
✅ Deve ter `queues=` ou `queue=self.queues` no SAQWorker init

#### 2. `_run_saq_worker` passa `burst`
```bash
grep -n "SAQWorker(" -A 3 aura/jobs/worker.py | grep burst
```
✅ Deve ter `burst=self.burst` no SAQWorker init

#### 3. `self.queues` é preservado de `__init__`
```bash
grep -n "self.queues = " aura/jobs/worker.py
```
✅ Deve ter `self.queues = queues or ["default"]`

#### 4. `self.burst` é preservado de `__init__`
```bash
grep -n "self.burst = " aura/jobs/worker.py
```
✅ Deve ter `self.burst = burst`

#### 5. Worker tests passam
```bash
pytest tests/test_jobs_worker.py -q --tb=short
```
✅ Todos testes passam

---

## Task 5: A8 — TaskRegistry Isolamento

### Critérios de Aceite

#### 1. `TaskRegistry.clear()` method existe
```bash
grep -n "def clear" aura/jobs/base.py
```
✅ Deve ter `clear()` classmethod

#### 2. Clear limpa `_registry`
```bash
grep -n "def clear" -A 3 aura/jobs/base.py | grep "_registry"
```
✅ Deve ter `cls._registry.clear()`

#### 3. Fixture `reset_task_registry` existe
```bash
grep -n "def reset_task_registry" tests/conftest.py
```
✅ Deve existir fixture

#### 4. Fixture é autouse
```bash
grep -n "reset_task_registry" -B 1 tests/conftest.py | grep autouse
```
✅ Deve ter `@pytest.fixture(autouse=True)`

#### 5. Fixture chama `TaskRegistry.clear()`
```bash
grep -n "def reset_task_registry" -A 5 tests/conftest.py | grep "clear"
```
✅ Deve chamar `TaskRegistry.clear()` antes e depois de yield

#### 6. Testes jobs passam
```bash
pytest tests/test_jobs.py tests/test_jobs_worker.py -q --tb=short
```
✅ Todos testes passam

---

## Task 6: mypy aura/ — 8 Erros Residuais

### Critério de Aceite Global

#### 1. mypy retorna 0 erros
```bash
python -m mypy aura/ --ignore-missing-imports
```
✅ **Output final deve ser: `Success: 0 errors in X source files`**

#### 2. Sem type: ignore (validar)
```bash
grep "# type: ignore" aura/ -r | wc -l
```
✅ Deve ter **zero** `# type: ignore` comentários (ou justificados)

#### 3. Testes ainda passam
```bash
pytest tests/ -q --tb=short
```
✅ Todos testes passam

---

## Task 7: test_tinker.py — 2 Falhas

### Critério de Aceite

#### 1. test_tinker.py passa
```bash
pytest tests/test_tinker.py -q --tb=short
```
✅ Todos testes passam

#### 2. Nenhuma falha residual
```bash
pytest tests/test_tinker.py -v
```
✅ Todos `PASSED` (nenhum `FAILED` ou `ERROR`)

#### 3. Fixture clean_sys_modules funciona
```bash
pytest tests/test_tinker.py -v --tb=short -k "discover"
```
✅ Testes de descoberta passam sem poluição entre si

---

## Verificação Final (Após Todas as Tasks)

### Comando Mestre de Validação

```bash
#!/bin/bash
set -e

echo "=== Wave 3 Verification ==="

# 1. C12
echo "✓ C12: DatabaseMiddleware fail-fast"
grep -q "_lazy_init_failed" aura/orm/middleware.py
grep -q "500\|Service Unavailable" aura/orm/middleware.py

# 2. C15
echo "✓ C15: Remover sync templates"
! grep -q "_render_component_sync" aura/templates/engine.py
test -f docs/decisions/ADR-002*.md

# 3. C3
echo "✓ C3: RateLimitGuard + LRU + headers"
grep -q "max_tracked_keys" aura/guards/rate_limit.py
grep -q "X-RateLimit" aura/guards/rate_limit.py
grep -q "Retry-After" aura/guards/rate_limit.py

# 4. A7
echo "✓ A7: AuraWorker queues/burst"
grep "SAQWorker(" aura/jobs/worker.py | grep -q "queues"
grep "SAQWorker(" aura/jobs/worker.py | grep -q "burst"

# 5. A8
echo "✓ A8: TaskRegistry isolamento"
grep -q "def clear" aura/jobs/base.py
grep -q "reset_task_registry" tests/conftest.py

# 6. mypy
echo "✓ mypy aura/ (0 erros)"
python -m mypy aura/ --ignore-missing-imports | grep -q "Success: 0 errors"

# 7. test_tinker
echo "✓ test_tinker.py passa"
pytest tests/test_tinker.py -q

# 8. Global
echo "✓ pytest (607+ testes)"
pytest tests/ -q | tail -1
python -m ruff check aura/ tests/ > /dev/null 2>&1 && echo "✓ ruff clean"

echo ""
echo "✅ WAVE 3 VERIFICADO COM SUCESSO"
```

### Salvar como `verify_wave3.sh` e executar:
```bash
chmod +x verify_wave3.sh
./verify_wave3.sh
```

---

## Matriz de Verificação Rápida

| # | Task | Arquivo | Verificação | Comando |
|----|------|---------|------------|---------|
| 1 | C12 | `aura/orm/middleware.py` | `_lazy_init_failed` existe | `grep "_lazy_init_failed"` |
| 2 | C15 | `aura/templates/engine.py` | Sem `_render_component_sync` | `! grep "_render_component_sync"` |
| 3 | C3 | `aura/guards/rate_limit.py` | `max_tracked_keys` + headers | `grep "max_tracked_keys\|X-RateLimit"` |
| 4 | A7 | `aura/jobs/worker.py` | `queues` e `burst` em SAQWorker | `grep "queues\|burst"` |
| 5 | A8 | `aura/jobs/base.py` | `clear()` method | `grep "def clear"` |
| 6 | mypy | `aura/*` | 0 erros | `mypy aura/ --ignore-missing-imports` |
| 7 | test_tinker | `tests/test_tinker.py` | Todos passam | `pytest tests/test_tinker.py -q` |

---

**Documento auxiliar:** Use para validar implementação de cada tarefa  
**Salvar como:** `docs/WAVE3_ACCEPTANCE_CRITERIA.md`  
**Executar:** Após cada task + verificação final completa

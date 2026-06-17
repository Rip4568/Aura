# Wave 3 — Produção & Estabilidade — Plano de Implementação

**Data:** 2026-06-17  
**Branch:** `fix/wave3-production-stability`  
**Versão alvo:** `1.3.0`  
**Baseline de testes:** 607 passando (mypy aura/: 8 erros residuais; test_tinker.py: 2 falhas)

---

## Resumo Executivo

Wave 3 cobre **7 tarefas críticas/altas** (obrigatórias) que resolvem gargalos de produção:

1. **C12** — `DatabaseMiddleware` fail-fast na inicialização lazy
2. **C15** — Remover componentes síncronos em templates async
3. **C3** — `RateLimitGuard` alinhar com headers do middleware + limite memória
4. **A7** — `AuraWorker` respeitar `queues`/`burst` em SAQ
5. **A8** — `TaskRegistry` isolamento global (singleton poluído entre testes)
6. **mypy aura/** — 8 erros residuais (jwt.py, admin/views.py, core/app.py, tinker.py)
7. **test_tinker.py** — 2 falhas

---

## Tarefas Críticas (Obrigatório Wave 3)

### Task 1: C12 — DatabaseMiddleware Fail-Fast

**ID:** `C12`  
**Arquivo:** `aura/orm/middleware.py`  
**Impacto:** Production readiness · Error handling  
**Breaking change:** Não

#### Problema Atual

Linhas 69–81: Quando `db._session_factory` é `None` (ex: lazy init falha):
- Log de warning é emitido
- Request **prossegue sem erro** (silenciosamente falha)
- Operações de BD dentro do handler → `RuntimeError` vago

```python
if db._session_factory is None:
    logger.warning("DatabaseMiddleware is active but db._session_factory is None...")
    await self.app(scope, receive, send)  # ❌ Prossegue sem erro!
    return
```

#### Solução

**Fail-fast** ao detectar inicialização impossível. Diferencia:
1. **Lazy init ainda não tentado** → tentar (status quo, aceitável)
2. **Lazy init já tentou, falhou** → `500 Service Unavailable` com body legível
3. **BD não está configurada** (envvars ausentes) → deixar prosseguir (teste com TestClient)

#### Critério de Aceite

- [ ] Se `db._session_factory is None` após `_try_lazy_init()`, retornar **500** com mensagem clara
- [ ] Resposta 500 tem `Content-Type: text/plain` e instruções (ex: "Set AURA__DATABASE__URL")
- [ ] Em contexto de teste (ex: `pytest` sem DB configurada), prossegue normalmente
- [ ] Adicionar flag `_lazy_init_failed: bool` para rastrear tentativa
- [ ] Log com `logger.error()` no path 500, não apenas warning

#### Arquivos a Modificar

```
aura/orm/middleware.py
  ├─ Adicionar `_lazy_init_failed: bool = False` em `__init__`
  ├─ Setar `_lazy_init_failed = True` se `_try_lazy_init()` falhar
  └─ Em `__call__`, se `_lazy_init_failed and db._session_factory is None`:
     └─ Retornar 500 (helpers em `aura/core/response.py` se necessário)
```

#### Contrato / API

Nenhuma quebra. A mudança **fortalece** o contrato: não silencia erros.

#### Testes de Verificação

```bash
# Verificar novo comportamento
grep -n "_lazy_init_failed" aura/orm/middleware.py
grep -n "500\|Service Unavailable" aura/orm/middleware.py

# Rodar testes ORM existentes
pytest tests/test_orm.py -q --tb=short
pytest tests/test_middleware.py -q --tb=short
```

#### Dependências

Nenhuma. Task independente.

---

### Task 2: C15 — Remover Componentes Síncronos em Templates Async

**ID:** `C15`  
**Arquivo:** `aura/templates/engine.py`  
**Impacto:** Async correctness · Performance  
**Breaking change:** Sim (componentes síncronos em templates deixarão de funcionar)

#### Problema Atual

Linhas 180–189: `_render_component_sync()` usa `asyncio.run_until_complete()` dentro de contexto Jinja2 síncrono:

```python
def _render_component_sync(self, name: str, **kwargs: Any) -> str:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    return loop.run_until_complete(self.render_component(name, **kwargs))
```

**Problema:** Em ambiente com event loop rodando, isso pode:
- Bloquear a loop (desastre em produção)
- Criar deadlock se `render_component` tentar acessar a loop atual
- Não respeita contexto assíncrono do template já sendo renderizado

#### Solução

**Opção A (Recomendado):** Remover `_render_component_sync()` inteiramente
- Forçar templates a usar `await component(...)` (Jinja2 async templates já suportam await)
- Migração: documentar no CHANGELOG
- Componentes que precisam de lógica síncrona devem **pré-computar** em Python

**Opção B:** Manter `_render_component_sync()` com warning
- Manter por compatibilidade
- Logar warning cada vez que é chamado
- Planar remoção em v2.0

**Implementar:** Opção A (mais limpo, força melhores práticas)

#### Critério de Aceite

- [ ] `_render_component_sync()` removido de `AuraTemplateEngine`
- [ ] `self._env.globals["component"]` aponta para `self.render_component` (async)
- [ ] Documentação em `aura/templates/engine.py` diz "use `await component(...)`"
- [ ] ADR-002 criado explicando mudança
- [ ] Testes que usam `component(...)` sem `await` → atualizados para `await component(...)`
- [ ] CHANGELOG documenta breaking change + migração

#### Arquivos a Modificar

```
aura/templates/engine.py
  ├─ Remover `_render_component_sync()` (linhas 180–189)
  ├─ Em __init__, linha 78:
  │  └─ `"component": self.render_component,` (era `self._render_component_sync`)
  └─ Atualizar docstring em `AuraTemplateEngine` → "Components must use `await component(...)`"

tests/
  ├─ tests/test_templates.py (search for `component(` without `await`)
  └─ Atualizar exemplos

docs/decisions/
  └─ ADR-002-async-templates-only.md (novo)
```

#### Contrato / API

**Breaking change**: `component(...)` em templates deixa de funcionar (deve ser `await component(...)`).

**Justificativa:**
- Facilita async-correctness
- Remove hack de `run_until_complete` em runtime
- Força padrão Jinja2 async nativo

#### Testes de Verificação

```bash
# Verificar remoção
grep -n "_render_component_sync" aura/templates/engine.py  # deve retornar vazio

# Verificar novo setup
grep -n "self.render_component" aura/templates/engine.py  # deve estar em __init__

# Rodar templates tests
pytest tests/test_templates.py -q --tb=short
```

#### Dependências

Nenhuma (isolado). Mas requer atualização de testes que usam templates.

---

### Task 3: C3 — RateLimitGuard Alinhar com Middleware + Headers

**ID:** `C3`  
**Arquivo:** `aura/guards/rate_limit.py`  
**Impacto:** Consistência · Production readiness  
**Breaking change:** Não (headers adicionados)

#### Problema Atual

`RateLimitGuard` (linhas 14–71):
1. **Memória não limitada**: `self._requests` é `defaultdict(list)` sem limpeza. Se atacado com muitas IPs diferentes, cresce sem limite.
2. **Headers inconsistentes**: Não retorna `X-RateLimit-*` headers quando rejeita. `RateLimitMiddleware` sim (linhas 108–114 em middleware/rate_limit.py).
3. **Sem `Retry-After`**: Middleware retorna `Retry-After`, Guard não.

```python
# Guard atual — sem headers
async def on_denied(self, request: Request) -> None:
    raise HTTPException(status_code=429, message=self.message)
```

vs.

```python
# Middleware — com headers
await send({
    "type": "http.response.start",
    "status": 429,
    "headers": [
        (b"retry-after", str(retry_after).encode()),
        (b"x-ratelimit-limit", str(self.max_requests).encode()),
        (b"x-ratelimit-remaining", b"0"),
    ],
})
```

#### Solução

1. **Adicionar headers** ao HTTPException ou criar resposta customizada
2. **Limitar memória** com LRU cache ou max size em `_requests`
3. **Sincronizar headers** com middleware: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`

#### Arquitetura Proposta

```python
class RateLimitGuard(Guard):
    def __init__(
        self,
        *,
        max_requests: int = 60,
        window_seconds: int = 60,
        key_func: Callable[[Request], str] | None = None,
        message: str = "Rate limit exceeded",
        max_tracked_keys: int = 10000,  # LRU limit
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.key_func = key_func or self._default_key
        self.message = message
        self.max_tracked_keys = max_tracked_keys
        self._requests: dict[str, list[float]] = {}
        self._key_order: list[str] = []  # Simples LRU via order de acesso

    async def can_activate(self, request: Request) -> bool:
        key = self.key_func(request)
        now = time.monotonic()
        window_start = now - self.window_seconds
        
        # Cleanup memoria
        if len(self._requests) > self.max_tracked_keys:
            self._cleanup_oldest_key()
        
        history = self._requests.get(key, [])
        self._requests[key] = [ts for ts in history if ts >= window_start]
        
        if len(self._requests[key]) >= self.max_requests:
            return False
        
        self._requests[key].append(now)
        # Track key order for LRU
        if key in self._key_order:
            self._key_order.remove(key)
        self._key_order.append(key)
        return True

    async def on_denied(self, request: Request) -> None:
        # Retornar headers compatíveis com middleware
        from aura.exceptions.http import HTTPException
        exc = HTTPException(
            status_code=429,
            message=self.message,
            headers={
                "X-RateLimit-Limit": str(self.max_requests),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(self.window_seconds),
            }
        )
        raise exc

    def _cleanup_oldest_key(self) -> None:
        """Remove oldest key to stay under max_tracked_keys."""
        if self._key_order:
            oldest = self._key_order.pop(0)
            self._requests.pop(oldest, None)
```

**Nota:** `HTTPException` já suporta `headers` dict? Verificar `aura/exceptions/http.py`.

#### Critério de Aceite

- [ ] `RateLimitGuard` aceita `max_tracked_keys` em `__init__`
- [ ] `_requests` dict nunca cresce acima de `max_tracked_keys` (LRU eviction)
- [ ] `on_denied()` retorna 429 com headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`
- [ ] Headers são idênticos em sintaxe aos de `RateLimitMiddleware`
- [ ] Novos testes verificam: (a) eviction LRU, (b) headers na resposta 429

#### Arquivos a Modificar

```
aura/guards/rate_limit.py
  ├─ Adicionar `max_tracked_keys` param
  ├─ Mudar `_requests: dict[str, list[float]] = {}` (remover defaultdict)
  ├─ Adicionar `_key_order: list[str] = []`
  ├─ Implementar `_cleanup_oldest_key()`
  └─ `on_denied()` → retornar HTTPException com headers

aura/exceptions/http.py
  └─ Verificar se `HTTPException.__init__` já suporta `headers` param
     (se não, adicionar)
```

#### Contrato / API

Não-breaking. Nova feature (`max_tracked_keys`), headers adicionados (backward-compatible).

#### Testes de Verificação

```bash
# Verificar nova signature
grep -n "max_tracked_keys" aura/guards/rate_limit.py
grep -n "_cleanup_oldest_key" aura/guards/rate_limit.py
grep -n "X-RateLimit" aura/guards/rate_limit.py

# Rodar guards tests
pytest tests/test_guards_auth.py -q --tb=short -k "rate_limit"

# Buscar testes que checam 429 headers
grep -r "429" tests/ | grep -i "header"
```

#### Dependências

- Task 3 depende de `HTTPException` suportar `headers`. Se não suportar → implementar em C3.

---

### Task 4: A7 — AuraWorker Respeitar queues/burst em SAQ

**ID:** `A7`  
**Arquivo:** `aura/jobs/worker.py`  
**Impacto:** Jobs correctness · Feature completeness  
**Breaking change:** Não (implementação de feature)

#### Problema Atual

Linhas 130–139: `_run_saq_worker()` cria `SAQWorker` mas **não passa `queues` nem `burst`**:

```python
async def _run_saq_worker(self) -> None:
    functions = [task_def.func for task_def in TaskRegistry.all().values()]
    saq_worker = SAQWorker(
        queue=self._backend._queue,  # ❌ Ignora self.queues
        functions=functions,
        concurrency=self._concurrency,
        # ❌ Falta: burst=self.burst
    )
```

**Problema:**
- `self.queues` (ex: `["default", "emails"]`) é ignorado → worker sempre processa só 1 queue
- `self.burst` é ignorado → worker nunca sai em modo burst (run-once and exit)
- CLI flags `--queue emails --burst` não funcionam

#### Solução

**Opção 1 (Simples):** Passar `queues` e `burst` para `SAQWorker`
- Verificar assinatura de `SAQWorker.__init__()` em SAQ upstream
- Se SAQ suporta, passar diretamente

**Opção 2 (Se SAQ não suporta múltiplas queues):** Looping manual
- Para cada queue em `self.queues`, criar worker separado
- Mais complexo, evitar

**Implementar:** Opção 1 (verifique SAQ docs primeiro)

#### Critério de Aceite

- [ ] `SAQWorker` recebe `queues=self.queues` (ou formato que SAQ espera)
- [ ] `SAQWorker` recebe `burst=self.burst`
- [ ] `aura worker --queue emails --queue backups --burst` processa ambas queues em burst
- [ ] Teste verifica que worker para quando queues estão vazias (burst mode)
- [ ] Teste verifica que worker continua rodando sem burst

#### Arquivos a Modificar

```
aura/jobs/worker.py
  ├─ `_run_saq_worker()` linha ~130:
  │  ├─ Adicionar queues ao SAQWorker
  │  └─ Adicionar burst ao SAQWorker
  └─ Atualizar docstring se necessário

tests/test_jobs_worker.py
  └─ Adicionar testes para queues múltiplas + burst
```

#### Contrato / API

Não-breaking. CLI comporta-se conforme documentado.

#### Verificação SAQ

Antes de implementar, verificar:
```bash
# Verificar assinatura SAQWorker
python -c "from saq import Worker; help(Worker.__init__)"
```

Se `Worker` aceita `queues` (list) e `burst` (bool), tudo bem.

#### Testes de Verificação

```bash
# Verificar parâmetros passados
grep -n "SAQWorker(" aura/jobs/worker.py | grep -E "queues|burst"

# Rodar worker tests
pytest tests/test_jobs_worker.py -q --tb=short
```

#### Dependências

Nenhuma (isolado).

---

### Task 5: A8 — TaskRegistry Isolamento Entre Testes

**ID:** `A8`  
**Arquivo:** `aura/jobs/base.py`, `tests/conftest.py`  
**Impacto:** Test isolation · Reliability  
**Breaking change:** Não

#### Problema Atual

`TaskRegistry` em `aura/jobs/base.py` é um singleton global:

```python
class TaskRegistry:
    _registry: dict[str, TaskDefinition] = {}
    
    @classmethod
    def register(cls, definition: TaskDefinition) -> None:
        cls._registry[definition.name] = definition
    
    @classmethod
    def all(cls) -> dict[str, TaskDefinition]:
        return cls._registry
```

**Problema:** Testes que usam `@task` decorator adicionam tasks ao registry. Se múltiplos testes rodam, tarefas de um teste vazam para outro (test pollution).

Exemplos:
- Teste A registra `send_email` task
- Teste B não quer `send_email`, mas ela está lá → B vê task de A
- Confusão em `TaskRegistry.all()` durante tests

#### Solução

**Opção 1:** Limpar registry em fixture
- Adicionar `reset_task_registry()` em `tests/conftest.py`
- Rodá-lo com `autouse=True` em cada teste

**Opção 2:** Fazer TaskRegistry mock-friendly
- Adicionar método `clear()` para limpeza
- Documentar que deve ser chamado entre testes

**Implementar:** Ambas (complementares)

#### Implementação

**aura/jobs/base.py:**
```python
class TaskRegistry:
    _registry: dict[str, TaskDefinition] = {}
    
    @classmethod
    def clear(cls) -> None:
        """Clear all registered tasks (for testing)."""
        cls._registry.clear()
    
    @classmethod
    def register(cls, definition: TaskDefinition) -> None:
        cls._registry[definition.name] = definition
    
    @classmethod
    def all(cls) -> dict[str, TaskDefinition]:
        return cls._registry
```

**tests/conftest.py:**
```python
@pytest.fixture(autouse=True)
def reset_task_registry() -> Generator[None, None, None]:
    """Reset TaskRegistry before and after each test."""
    from aura.jobs.base import TaskRegistry
    
    TaskRegistry.clear()
    yield
    TaskRegistry.clear()
```

#### Critério de Aceite

- [ ] `TaskRegistry.clear()` método adicionado
- [ ] `reset_task_registry()` fixture adicionada em conftest.py com `autouse=True`
- [ ] Testes que usam `@task` rodam isolados (sem vazamento)
- [ ] `pytest tests/ -q --tb=short` passa sem poluição entre testes

#### Arquivos a Modificar

```
aura/jobs/base.py
  └─ Adicionar `clear()` classmethod

tests/conftest.py
  └─ Adicionar `reset_task_registry()` fixture com `autouse=True`
```

#### Contrato / API

Não-breaking. `clear()` é novo método (opt-in).

#### Testes de Verificação

```bash
# Verificar clear() existe
grep -n "def clear" aura/jobs/base.py

# Verificar fixture existe
grep -n "reset_task_registry" tests/conftest.py

# Rodar testes
pytest tests/ -q --tb=short
```

#### Dependências

Nenhuma (isolado).

---

### Task 6: mypy aura/ — 8 Erros Residuais

**ID:** `mypy`  
**Arquivo:** Múltiplos (jwt.py, admin/views.py, core/app.py, tinker.py)  
**Impacto:** Type safety · CI/CD  
**Breaking change:** Não

#### Estado Atual

```bash
python -m mypy aura/ --ignore-missing-imports
```

Retorna **~8 erros** em:
- `aura/guards/jwt.py` (2–3 erros)
- `aura/admin/views.py` (2–3 erros)
- `aura/core/app.py` (1–2 erros)
- `aura/cli/commands/tinker.py` (1–2 erros)

#### Investigação Necessária

Rodar mypy verbose para ver erros exatos:
```bash
python -m mypy aura/ --ignore-missing-imports --show-error-codes
```

Erros típicos em Aura:
- `Any` retornado onde tipo específico esperado
- `Optional[X]` não checado antes de usar
- Importação de módulo opcional não guarda com `TYPE_CHECKING`

#### Processo de Correção

Para cada arquivo com erro:

1. **Ler** arquivo completo
2. **Identificar** linha exata do erro (mypy mostra linha)
3. **Corrigir** com:
   - Type annotation explícita
   - `if TYPE_CHECKING:` para imports opcionais
   - Cast se necessário (`cast(Type, value)`)
   - `# type: ignore` como **último recurso** (nunca primeira opção)
4. **Verificar** que correção não quebra testes

#### Critério de Aceite

- [ ] `python -m mypy aura/ --ignore-missing-imports` retorna **0 erros**
- [ ] Nenhum `# type: ignore` foi adicionado (exceto se absolutamente necessário, com justificativa em comment)
- [ ] Todas correções preservam `pytest tests/ -q --tb=short` passando

#### Arquivos Prováveis

```
aura/guards/jwt.py
  ├─ Linha ~XX: _decode() retorna Any ou None?
  └─ Linha ~XX: Tipagem de claim validation

aura/admin/views.py
  ├─ Linha ~XX: Tipagem de session property
  ├─ Linha ~XX: Tipagem de form parsing
  └─ Linha ~XX: Dict contexts

aura/core/app.py
  ├─ Linha ~XX: Exception handler typing
  └─ Linha ~XX: Optional middleware

aura/cli/commands/tinker.py
  ├─ Linha ~XX: discover_project_objects return type
  └─ Linha ~XX: Tipagem de descoberta de módulos
```

#### Testes de Verificação

```bash
# Verificar zero erros
python -m mypy aura/ --ignore-missing-imports

# Se houver ainda erros, mostrar:
python -m mypy aura/ --ignore-missing-imports --show-error-codes
```

#### Dependências

Nenhuma (isolado, mas requer análise individual de cada erro).

---

### Task 7: test_tinker.py — 2 Falhas

**ID:** `test_tinker`  
**Arquivo:** `tests/test_tinker.py`  
**Impacto:** CLI reliability · Test coverage  
**Breaking change:** Não

#### Estado Atual

```bash
pytest tests/test_tinker.py -v
```

Retorna **2 falhas** (detalhes a determinar na execução).

#### Investigação Necessária

Rodar teste com traceback completo:
```bash
pytest tests/test_tinker.py -v --tb=long
```

Analisar output para determinar raiz (ex: import error, mock issue, environment).

#### Cenários Prováveis

1. **Import error em descoberta de módulos**: `discover_project_objects()` falha em importing módulo criado temporariamente
   - Solução: Melhorar handling de exceção ou fixture cleanup
   
2. **Fixture `clean_sys_modules` inadequada**: Módulos vazam entre testes
   - Solução: Melhorar fixture para limpar `sys.modules` mais agressivamente
   
3. **Mock de `code.interact` ou IPython incompleto**
   - Solução: Atualizar mock spec ou usar `unittest.mock.patch.object`

#### Critério de Aceite

- [ ] `pytest tests/test_tinker.py -q` passa sem falhas
- [ ] Todos testes em tinker executam e coletam (sem collection errors)
- [ ] Fixture `clean_sys_modules` limpa sys.modules e sys.path corretamente

#### Testes de Verificação

```bash
# Rodar com verbose
pytest tests/test_tinker.py -v --tb=short

# Rodar sem tinker para ver se rest passa
pytest tests/ -q --tb=short -k "not tinker"
```

#### Dependências

Nenhuma (isolado).

---

## Tarefas Médias (Se Couber na Wave)

### Task M1: RequestLogInterceptor — Redação de Headers/Body Sensíveis

**ID:** `M1`  
**Arquivo:** `aura/middleware/logging.py` ou similar  
**Impacto:** Security · Logging  
**Prioridade:** Média

**Resumo:** Interceptor que redacta Authorization, X-API-Key, Cookie headers e request bodies que contêm `password`, `token`, etc.

**Critério básico:**
```python
# Antes
[2026-06-17 ...] Authorization: Bearer eyJ0eXAi...
                 Body: {"password": "secret123", "email": "user@..."}

# Depois
[2026-06-17 ...] Authorization: Bearer ***[REDACTED]***
                 Body: {"password": "***[REDACTED]***", "email": "user@..."}
```

---

### Task M2: CompressionMiddleware — gzip_level Ignorado

**ID:** `M2`  
**Arquivo:** `aura/middleware/compression.py`  
**Impacto:** Performance tuning  
**Prioridade:** Média

**Resumo:** `gzip_level` param não é passado a Starlette's `GZipMiddleware`.

```python
# Correto:
from starlette.middleware.gzip import GZipMiddleware

# Adicionar gzip_level ao middleware init
GZipMiddleware(app, minimum_size=1000, gzip_level=6)
```

---

### Task M3: OpenAPI securitySchemes + Router.tags Merge

**ID:** `M3`  
**Arquivo:** `aura/schema/openapi.py`  
**Impacto:** Documentation completeness  
**Prioridade:** Média

**Resumo:** OpenAPI schema não inclui `securitySchemes` (para JWT, API Key) e `Router.tags` não são merged em operações.

---

## Mapa de Dependências e Paralelização

```
┌─────────────────────────────────────────────────────────┐
│ Task 1: C12 (DatabaseMiddleware fail-fast)              │
│ • Independente                                           │
│ • Pode rodar em paralelo                                 │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Task 2: C15 (Remover componentes síncronos)             │
│ • Independente (mas impacta testes)                     │
│ • Pode rodar em paralelo                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Task 3: C3 (RateLimitGuard headers + LRU)               │
│ ├─ Depende: HTTPException suporta headers?             │
│ │  └─ Se não, implementar em task 3 mesmo              │
│ └─ Pode rodar em paralelo                              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Task 4: A7 (AuraWorker queues/burst SAQ)               │
│ • Independente                                           │
│ • Pode rodar em paralelo                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Task 5: A8 (TaskRegistry isolamento)                    │
│ • Independente                                           │
│ • Pode rodar em paralelo                                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Task 6: mypy aura/ (8 erros)                            │
│ • Executa APÓS outras tasks (para não ser mascarado)   │
│ • Ou em paralelo (se erros são isolados)                │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Task 7: test_tinker.py (2 falhas)                       │
│ • Executa APÓS outras tasks                             │
│ • Pode depender de mypy (se erro de tipo)               │
└─────────────────────────────────────────────────────────┘

RECOMENDAÇÃO DE PARALELIZAÇÃO:
───────────────────────────────
Fase 1 (paralelo): Tasks 1, 2, 3, 4, 5
Fase 2 (sequencial): Task 6 (mypy global)
Fase 3 (sequencial): Task 7 (test_tinker com estado limpo)
```

---

## ADRs Necessários

### ADR-002: Templates Async-Only (C15)

**Status:** Proposto  
**Data:** 2026-06-17

**Contexto:**
Aura templates engine usa Jinja2 em modo async (`enable_async=True`). Porém, registra `component` como função síncrona que chama `run_until_complete()` internamente — padrão perigoso em environments async.

**Decisão:**
Remover `_render_component_sync()` e forçar uso de `await component(...)` em templates.

**Justificativa:**
- Elimina risco de deadlock em production
- Força async-correctness
- Alinha com padrão Jinja2 async nativo
- Simplifica código (+9 linhas, -30)

**Consequências:**
- Breaking change: templates antigas com `component(...)` sem `await` quebram
- Melhoria: melhor error handling (erros async propagam corretamente)
- Migração: documentado em CHANGELOG

---

## Critérios de Aceite Globais

```bash
# Antes de marcar Wave 3 como completa:

# 1. Todas tasks completadas
pytest tests/ -q --tb=no          # 607+ passando, todas tasks implementadas

# 2. Tipo safety
python -m mypy aura/ --ignore-missing-imports  # 0 erros

# 3. Code quality
python -m ruff check aura/ tests/  # 0 issues

# 4. Específicas por task:
grep -n "fail.*fast\|500\|Service" aura/orm/middleware.py      # C12
grep -n "_render_component_sync" aura/templates/engine.py      # C15 (vazio)
grep -n "max_tracked_keys\|X-RateLimit" aura/guards/rate_limit.py  # C3
grep -n "queues.*burst" aura/jobs/worker.py                    # A7
grep -n "clear" aura/jobs/base.py                              # A8
grep -n "reset_task_registry" tests/conftest.py                # A8 (tests)

# 5. Commits
git log --oneline fix/wave3-production-stability | head -20    # Histórico limpo
```

---

## Checklist de Implementação

### Preparação
- [ ] Criar branch `fix/wave3-production-stability` de `main`
- [ ] Atualizar `CLAUDE.md` com status Wave 3
- [ ] Ler tudo em `docs/pending.md` (já feito acima)

### Task 1: C12
- [ ] Ler `aura/orm/middleware.py` completo
- [ ] Implementar `_lazy_init_failed` flag
- [ ] Retornar 500 se init falha
- [ ] Testes passam
- [ ] grep verificações

### Task 2: C15
- [ ] Ler `aura/templates/engine.py` completo
- [ ] Remover `_render_component_sync()`
- [ ] Atualizar globals
- [ ] Atualizar testes que usam `component(...)`
- [ ] Criar ADR-002
- [ ] grep verificações

### Task 3: C3
- [ ] Verificar assinatura `HTTPException` (suporta headers?)
- [ ] Ler `aura/guards/rate_limit.py` completo
- [ ] Implementar `max_tracked_keys` + LRU
- [ ] Adicionar headers a `on_denied()`
- [ ] Testes novo comportamento
- [ ] grep verificações

### Task 4: A7
- [ ] Verificar `SAQWorker` assinatura (SAQ docs)
- [ ] Ler `aura/jobs/worker.py` completo
- [ ] Passar `queues` e `burst` a SAQWorker
- [ ] Testes CLI `--queue` / `--burst`
- [ ] grep verificações

### Task 5: A8
- [ ] Ler `aura/jobs/base.py` completo
- [ ] Adicionar `TaskRegistry.clear()`
- [ ] Adicionar fixture em `tests/conftest.py`
- [ ] Testes isolamento
- [ ] grep verificações

### Task 6: mypy
- [ ] Rodar mypy com `--show-error-codes`
- [ ] Para cada erro: ler arquivo, entender, corrigir
- [ ] Verificar testes ainda passam
- [ ] mypy 0 erros

### Task 7: test_tinker
- [ ] Rodar `pytest tests/test_tinker.py -v --tb=long`
- [ ] Diagnosticar 2 falhas
- [ ] Corrigir
- [ ] Verificar isolamento com `clean_sys_modules`
- [ ] Todos testes passam

### Finalização
- [ ] Atualizar `docs/pending.md`: marcar tarefas com [x]
- [ ] Atualizar `CHANGELOG.md`: documentar breaking changes (C15)
- [ ] Versão em `pyproject.toml`: 1.2.0 → 1.3.0
- [ ] Atualizar `CLAUDE.md` com Wave 3 completa
- [ ] git commit com mensagem descritiva
- [ ] Verificações finais: pytest, mypy, ruff

---

## Dicas de Implementação

### Para o Engenheiro

1. **Leia antes de mexer**: Sempre ler arquivo completo antes de editar
2. **Teste isolado**: Cada task é independente — pode rodar em paralelo, mas verifique ao final
3. **Tipo safety**: Mypy strict — nenhum `Any` injustificado
4. **Documentação**: Docstrings em todo código novo/modificado
5. **Git limpo**: Um commit por task, mensagem descritiva

### Ordem Recomendada

Se implementando sequencialmente (não paralelo):
1. Task 5 (A8) — mais simples, fixture cleanup
2. Task 1 (C12) — middleware, sem deps
3. Task 4 (A7) — worker, simples
4. Task 3 (C3) — guards, requer verificação HTTPException
5. Task 2 (C15) — templates, impacta testes
6. Task 6 (mypy) — global, após outros
7. Task 7 (test_tinker) — final, com estado limpo

---

## Estimativa de Esforço

| Task | Complexidade | Tempo Estimado | Notas |
|------|-------------|----------------|-------|
| C12  | Média       | 45 min         | Fail-fast, logging |
| C15  | Alta        | 1h 30min       | Breaking, impacta testes |
| C3   | Média       | 1h             | LRU, headers |
| A7   | Baixa       | 30 min         | Config passthrough |
| A8   | Baixa       | 30 min         | Fixture, clear() |
| mypy | Variável    | 1-2h           | Depende de erros |
| test_tinker | Média | 45 min         | Diagnóstico + fix |

**Total estimado (paralelo):** 2h 30min – 3h 30min  
**Total estimado (sequencial):** 5–6h

---

## Referências

- `docs/pending.md` — roadmap principal
- `docs/decisions/ADR-001-security-hardening.md` — contexto Wave 1–2
- `CLAUDE.md` — protocolo de trabalho
- `README.md` — visão geral Aura
- `pyproject.toml` — deps, versão, configurações

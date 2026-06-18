# ADR-005: Database Job Backend (Wave 9)

**Status:** Aceito  
**Data:** 2026-06-17  
**Contexto:** Wave 9 — `fix/wave9-database-jobs`

---

## Contexto

Aura já oferecia filas via `MemoryBackend` (dev/test) e `SAQBackend` (Redis). Muitos apps em produção já possuem PostgreSQL ou SQLite async e não querem operar Redis só para jobs. Wave 9 adiciona um backend SQL persistente que reutiliza o mesmo `DatabaseManager` e o contrato `TaskBackend` existente.

---

## Decisões

### 1. Modelo `AuraJob` + tabela `aura_jobs`

**Decisão:** Jobs são persistidos na tabela `aura_jobs` via modelo SQLAlchemy `AuraJob` (`aura/jobs/models.py`), registrado em `_AuraRegistry`. Campos principais:

| Campo | Uso |
|-------|-----|
| `id` | UUID (PK) |
| `task_name`, `queue` | Roteamento e lookup no `TaskRegistry` |
| `args_json`, `kwargs_json` | Serialização JSON dos argumentos |
| `status` | `pending` → `running` → `success` / `failed` |
| `retry_count`, `max_retries` | Política de retry por task |
| `scheduled_at` | Delay / agendamento (`delay` em `enqueue`) |
| `started_at`, `completed_at`, `error`, `result_json` | Auditoria e consulta de resultado |

**Motivo:** Schema explícito e consultável; histórico de jobs sem infra extra.

**Breaking:** Não — API nova; tabela criada via `create_all` no `startup()`.

---

### 2. `DatabaseBackend` implementa `TaskBackend`

**Decisão:** `DatabaseBackend` (`aura/jobs/backends/database.py`) implementa `enqueue`, `get_result`, `startup` e `shutdown`. Métodos adicionais de worker: `claim_pending_jobs`, `has_pending_jobs`, `mark_success`, `mark_retry`, `mark_failed`.

**Motivo:** `@task` e dispatch permanecem backend-agnostic; só o worker conhece claim/mark.

**Extra:** `[sqlalchemy]` — lazy `ImportError` com hint de instalação.

**Breaking:** Não.

---

### 3. Worker com polling e `FOR UPDATE SKIP LOCKED`

**Decisão:** `AuraWorker` detecta `DatabaseBackend` e inicia N loops de polling (`concurrency`). Cada loop:

1. `claim_pending_jobs(queues, limit=1)` — jobs `PENDING` com `scheduled_at <= now`, ordenados por `created_at`.
2. Em **PostgreSQL**: `SELECT … FOR UPDATE SKIP LOCKED` + transição atômica para `RUNNING`.
3. Em **outros dialetos** (ex. SQLite): optimistic locking via `UPDATE … WHERE status = pending RETURNING`.
4. Sem jobs: `asyncio.sleep(0.5)`; modo `--burst` encerra quando a fila esvazia.
5. Execução via `TaskRegistry` com timeout, retry (`mark_retry`) e falha definitiva (`mark_failed`).

**Motivo:** `SKIP LOCKED` evita contenção entre workers PostgreSQL; fallback otimista mantém dev/test em SQLite.

**Breaking:** Não.

---

### 4. Config `AURA__JOBS__BACKEND=database`

```python
# JobsConfig (env prefix JOBS_ → AURA__JOBS__)
backend: str = "memory"  # memory | database | (saq via broker_url)
broker_url: str = "redis://localhost:6379"
default_queue: str = "default"
max_workers: int = 4
```

**Decisão:** `_get_default_backend()` em `aura/jobs/decorators.py` seleciona:

| Condição | Backend |
|----------|---------|
| `AURA__JOBS__BACKEND=database` | `DatabaseBackend` |
| `AURA__JOBS__BROKER_URL` definido | `SAQBackend` |
| (default) | `MemoryBackend` |

`DatabaseBackend` usa `AURA__DATABASE__URL` (ou `database_url` no construtor) quando não recebe `DatabaseManager` injetado.

**Motivo:** Mesmo padrão de config do restante do framework; zero Redis obrigatório.

**Breaking:** Não — campo `backend` novo com default `memory`.

---

### 5. Trade-offs vs SAQ / Redis

| Aspecto | `DatabaseBackend` | `SAQBackend` (Redis) |
|---------|-------------------|----------------------|
| Infra | Reutiliza DB existente | Requer Redis |
| Latência | Polling (~500 ms idle) | Push nativo, baixa latência |
| Throughput | Limitado por polling/locks | Alto (estruturas in-memory) |
| Multi-worker | `SKIP LOCKED` (PG); SQLite single-writer | Consumer groups SAQ |
| Persistência | SQL nativo, consultável | Redis AOF/RDB |
| Histórico | Linhas em `aura_jobs` | Depende de config SAQ |
| Dev local | SQLite sem Redis | Redis local ou container |

**Decisão:** `DatabaseBackend` é a opção **sem Redis** para cargas moderadas e apps que já têm SQL async. SAQ permanece recomendado para alto volume e latência sub-segundo.

**Breaking:** Não.

---

## Fora de escopo

- Limpeza automática / TTL de linhas `aura_jobs`
- Dead-letter queue dedicada
- Prioridade de fila além de `created_at` FIFO
- Migrations Alembic dedicadas (usa `create_all` no startup)

---

## Consequências

- Apps com `[sqlalchemy]` podem enfileirar jobs sem Redis; `aura worker` processa via polling.
- PostgreSQL em produção multi-worker com claim seguro; SQLite adequado para dev e single-worker.
- `@task`, retry e `get_result` funcionam igual aos outros backends; troca via env var.
- Carga alta ou latência crítica devem continuar em SAQ/Redis.

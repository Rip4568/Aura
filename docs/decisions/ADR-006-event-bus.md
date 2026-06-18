# ADR-006: EventBus (Wave 10)

**Status:** Aceito  
**Data:** 2026-06-17  
**Contexto:** Wave 10 — `fix/wave10-event-bus`

---

## Contexto

Aura precisa de pub/sub in-process e distribuído para desacoplar domínios (ex.: `user.created` → envio de e-mail, auditoria) sem acoplar handlers ao HTTP. Jobs (SAQ/database) cobrem trabalho assíncrono com retry; o EventBus cobre notificação de eventos com fan-out a múltiplos subscribers.

Wave 11 trará RabbitMQ/Kafka; Wave 10 entrega contrato estável e dois backends: memória (dev/test) e Redis Streams (produção leve).

---

## Decisões

### 1. Contrato `EventBus` + `EventEnvelope`

**Decisão:** Todo evento é um `EventEnvelope` com `topic`, `payload`, `event_id` (UUID) e `timestamp` (UTC). Backends implementam `publish`, `subscribe`, `startup` e `shutdown`.

**Motivo:** Payload tipado pelo produtor; metadados uniformes para tracing e idempotência futura.

**Breaking:** Não — API nova.

---

### 2. Backends: `memory` e `redis_streams`

| Backend | Uso | Extra |
|---------|-----|-------|
| `memory` | Dev, testes, single-process | — |
| `redis_streams` | Multi-process / multi-host | `[redis]` |

**Decisão:** `InMemoryEventBus` usa filas `asyncio` por tópico com fan-out a subscribers. `RedisStreamsEventBus` usa `XADD` / `XREADGROUP` com prefixo configurável (`aura:events:`).

**Motivo:** Redis Streams já está no ecossistema Aura (rate limit, SAQ); evita nova dependência obrigatória.

**Breaking:** Não.

---

### 3. `@on_event("topic")` + `EventHandlerRegistry`

**Decisão:** Decorator registra handlers async em `EventHandlerRegistry` (topic → handlers). Handlers em controllers/providers são descobertos via metadata `__aura_event__` no startup.

**Motivo:** Mesmo padrão de `@task` / `@get`; descoberta automática via `ModuleRegistry`.

**Breaking:** Não.

---

### 4. Config `EventsConfig` (opt-in)

```python
events.enabled: bool = False
events.backend: str = "memory"  # memory | redis_streams
events.redis_url: str = "redis://localhost:6379"
events.stream_prefix: str = "aura:events:"
```

**Decisão:** EventBus desligado por padrão. `Aura(events_bus=...)` ou `events.enabled=True` ativa wiring no `_on_startup`.

**Motivo:** Zero overhead para apps que não usam eventos.

**Breaking:** Não.

---

### 5. `AuraEventsModule`

**Decisão:** Módulo opcional com `on_startup` que inicializa o bus, registra handlers e inicia consumers — espelhando `AuraTemplateModule`.

**Motivo:** Integração explícita para quem prefere módulo dedicado; auto-wiring cobre o caso `events.enabled=True`.

**Breaking:** Não.

---

## Fora de escopo (Wave 11)

- RabbitMQ / Kafka backends
- Dead-letter queues e retry policy no bus
- Schema registry / validação Pydantic por tópico

---

## Consequências

- Apps podem publicar eventos sem Redis; testes usam `InMemoryEventBus`.
- Produção multi-worker usa Redis Streams com consumer groups.
- Handlers devem ser idempotentes quando `redis_streams` estiver ativo (at-least-once).

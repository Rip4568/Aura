# ADR-007: Message Brokers (Wave 11)

**Status:** Aceito  
**Data:** 2026-06-17  
**Contexto:** Wave 11 — `fix/wave11-message-brokers` (base: `fix/wave10-event-bus`)

---

## Contexto

Wave 10 entregou `EventBus` com backends `memory` e `redis_streams`. Produção enterprise frequentemente exige RabbitMQ (AMQP, routing flexível) ou Kafka (log distribuído, alto throughput). NestJS expõe `@EventPattern` (fire-and-forget) e `@MessagePattern` (request/response) para microserviços — Aura adota o mesmo modelo de DX.

---

## Decisões

### 1. Backends opcionais: `rabbitmq` e `kafka`

| Backend | Pacote | Extra |
|---------|--------|-------|
| `rabbitmq` | `aio-pika` | `[rabbitmq]` |
| `kafka` | `aiokafka` | `[kafka]` |

**Decisão:** `RabbitMQEventBus` usa `connect_robust`, exchange tipo `topic`, routing key = nome do tópico. `KafkaEventBus` usa producer/consumer `aiokafka` com commit manual após handler.

**Motivo:** Dependências opcionais; lazy `ImportError` com hint de instalação.

**Breaking:** Não — API nova.

---

### 2. Decorators NestJS-style

**Decisão:**

- `@EventPattern("topic")` — handler fire-and-forget; metadata `__aura_message__` com `pattern: "event"`.
- `@MessagePattern("topic")` — handler request/response; metadata `__aura_message__` com `pattern: "message"`.

Handlers em controllers/providers são descobertos no startup (mesmo fluxo de `@on_event`).

**Motivo:** Familiaridade para equipes NestJS; separação clara entre eventos e RPC.

**Breaking:** Não.

---

### 3. `MessagingClient`

**Decisão:** Cliente fino sobre o bus ativo:

- `emit(topic, payload)` → `publish` (sem resposta).
- `send(topic, payload) -> response` → RPC via `reply_to` (RabbitMQ) ou reply topic + `correlation_id` (Kafka).

Backends sem suporte a RPC levantam `RuntimeError` em `send()`.

**Breaking:** Não.

---

### 4. Config `EventsConfig` estendida

```python
backend: str = "memory"  # memory | redis_streams | rabbitmq | kafka
rabbitmq_url: str = "amqp://guest:guest@localhost/"
kafka_bootstrap_servers: str = "localhost:9092"
kafka_consumer_group: str = "aura"
```

**Breaking:** Não — campos novos com defaults.

---

### 5. Semântica de entrega

- RabbitMQ/Kafka: **at-least-once**; handlers devem ser idempotentes.
- Kafka: commit após processamento bem-sucedido do handler.
- Request/response: timeout configurável (default 30s) no client.

---

## Fora de escopo

- Dead-letter queues e retry policy no bus
- Schema registry / validação Pydantic por tópico
- Transações Kafka exactly-once

---

## Consequências

- Apps podem trocar backend via `EventsConfig` sem mudar handlers.
- `memory` / `redis_streams` continuam válidos; `send()` só funciona em `rabbitmq` e `kafka`.
- Testes usam mocks de `aio-pika` / `aiokafka` com `skipif` quando extras não instalados.

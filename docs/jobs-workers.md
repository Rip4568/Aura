# Jobs, Workers & Tarefas Agendadas

## O Problema com Celery

O Celery domina o ecossistema Python há 15 anos — mas foi projetado para um mundo diferente:

- **Não é async-native** — usa threads/multiprocessing, não coroutines
- **Acknowledge-early por padrão** — a task é marcada como "feita" antes de executar; se o worker morrer, a task se perde
- **Configuração complexa** — `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TASK_SERIALIZER`... dezenas de settings
- **Worker isolado** — não compartilha o contexto da aplicação (DI, config, ORM)
- **Sem suporte a `async def`** nativo (a task vira síncrona internamente)

O Aura usa **SAQ (Simple Async Queue)** em produção — <5ms de latência, async-native, compartilha o mesmo event loop da aplicação.

---

## Registrando uma Task

```python
from aura.jobs.decorators import task

@task(queue="emails", retry=3, timeout=30)
async def send_welcome_email(user_id: int, email: str) -> None:
    """Envia email de boas-vindas para novo usuário."""
    # Aqui você pode usar serviços injetados via DI
    await email_service.send(
        to=email,
        template="welcome",
        context={"user_id": user_id},
    )
```

### Parâmetros do decorator `@task`

| Parâmetro | Tipo | Padrão | Descrição |
|---|---|---|---|
| `queue` | `str` | `"default"` | Fila destino |
| `retry` | `int` | `0` | Tentativas em caso de falha |
| `timeout` | `int \| None` | `None` | Timeout em segundos |
| `priority` | `int` | `0` | Maior número = maior prioridade |
| `name` | `str \| None` | `None` | Override do nome (padrão: `módulo.função`) |

---

## Disparando Tasks

```python
# Dispatch assíncrono (fire-and-forget)
await send_welcome_email.dispatch(user_id=1, email="user@example.com")

# Com delay (executa daqui 5 minutos)
await send_welcome_email.dispatch(
    user_id=1,
    email="user@example.com",
    delay=300,  # segundos
)

# Aguardar resultado (útil em testes)
result = await send_welcome_email.dispatch(user_id=1, email="user@example.com")
final = await send_welcome_email.wait_for_result(result.task_id, timeout=10)
print(final.status)  # TaskStatus.SUCCESS
```

### Disparando de dentro de um Controller/Service

```python
from aura import post, Body
from aura.tasks.email import send_welcome_email  # importa a task

class AuthController:
    @post("/auth/register", status=201)
    async def register(
        self,
        body: Annotated[RegisterDTO, Body()],
    ) -> UserResponse:
        user = await self.auth_service.register(body)
        
        # Dispara a task de email em background — não bloqueia a resposta
        await send_welcome_email.dispatch(
            user_id=user.id,
            email=user.email,
        )
        
        return user  # responde imediatamente ao cliente
```

---

## Tarefas Agendadas (Cron)

```python
from aura.jobs.decorators import periodic

# Executa todo dia às 08:00
@periodic(cron="0 8 * * *")
async def daily_digest() -> None:
    await report_service.send_daily_report()

# Executa a cada 15 minutos
@periodic(cron="*/15 * * * *")
async def sync_external_api() -> None:
    await integration.sync()

# Executa toda segunda-feira às 09:00 E também na startup do worker
@periodic(cron="0 9 * * 1", run_on_startup=True)
async def weekly_cleanup() -> None:
    await db_service.cleanup_old_records(days=90)
```

### Referência de Expressões Cron

```
┌───── minuto (0-59)
│ ┌───── hora (0-23)
│ │ ┌───── dia do mês (1-31)
│ │ │ ┌───── mês (1-12)
│ │ │ │ ┌───── dia da semana (0-7, dom=0 ou 7)
│ │ │ │ │
* * * * *

"0 8 * * *"     → todo dia às 08:00
"*/15 * * * *"  → a cada 15 minutos
"0 0 1 * *"     → 1º dia de cada mês à meia-noite
"0 9 * * 1-5"   → seg a sex às 09:00
"30 18 * * 5"   → sexta-feira às 18:30
```

---

## Backends

### MemoryBackend (desenvolvimento / testes)

```python
from aura.jobs.backends.memory import MemoryBackend

# Usado automaticamente quando nenhum backend é configurado
backend = MemoryBackend(concurrency=4)  # 4 workers paralelos
await backend.startup()

# Em testes
async def test_welcome_email():
    backend = MemoryBackend()
    await backend.startup()
    
    result = await send_welcome_email.dispatch(user_id=1, email="test@example.com")
    final = await backend.wait_for_result(result.task_id, timeout=5)
    
    assert final.status == TaskStatus.SUCCESS
    
    await backend.shutdown()
```

**Características:**
- ✅ Zero configuração
- ✅ Tasks executam no mesmo processo
- ✅ Ideal para testes e desenvolvimento
- ❌ Não persiste entre restarts
- ❌ Não escala para múltiplas instâncias

### SAQ Backend (produção)

```python
# config .env
AURA__JOBS__BROKER_URL=redis://localhost:6379/0

# main.py — Aura configura automaticamente baseado na URL
app = Aura(
    modules=[...],
    # SAQ é detectado quando AURA__JOBS__BROKER_URL está definido
)
```

**Características:**
- ✅ Persistência via Redis
- ✅ <5ms de latência
- ✅ Async-native (mesmo event loop)
- ✅ Múltiplos workers / múltiplos processos
- ✅ Dashboard de monitoramento
- ✅ Retry com backoff exponencial
- ✅ Dead letter queue
- ✅ Suporte a cron nativo

---

## Rodando o Worker

```bash
# Iniciar o worker (processa todas as filas)
aura worker

# Fila específica
aura worker --queue emails

# Múltiplas filas com prioridades
aura worker --queue critical --queue default --queue bulk

# Com concorrência customizada
aura worker --concurrency 10

# Com reload automático (desenvolvimento)
aura worker --reload
```

---

## Estrutura Recomendada de Projeto

```
my_api/
├── users/
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── email_tasks.py      # @task(queue="emails")
│   │   └── cleanup_tasks.py    # @periodic(cron="0 2 * * *")
│   ├── service.py
│   └── controller.py
├── notifications/
│   └── tasks/
│       └── push_tasks.py
└── main.py
```

```python
# users/tasks/email_tasks.py
from aura.jobs.decorators import task

@task(queue="emails", retry=3, timeout=60)
async def send_welcome_email(user_id: int, email: str) -> None:
    ...

@task(queue="emails", retry=2, timeout=30)
async def send_password_reset(email: str, token: str) -> None:
    ...

@task(queue="emails", priority=10)  # alta prioridade
async def send_security_alert(user_id: int, event: str) -> None:
    ...
```

---

## Monitoramento e Observabilidade

```python
# Verificar status de uma task
result = await backend.get_result(task_id)
print(result.status)    # PENDING, RUNNING, SUCCESS, FAILED
print(result.started_at)
print(result.finished_at)
print(result.error)     # mensagem de erro se FAILED
print(result.traceback) # stack trace completo

# Listar tasks pendentes de uma fila
pending = await backend.list_pending(queue="emails")
print(f"{len(pending)} emails na fila")
```

---

## Retry e Tratamento de Erros

```python
@task(queue="payments", retry=5, timeout=120)
async def process_payment(order_id: int, amount: float) -> dict:
    try:
        result = await payment_gateway.charge(order_id, amount)
        return result
    except TemporaryNetworkError:
        # Re-raise para acionar o retry automático
        raise
    except PermanentPaymentError as e:
        # Não vai tentar de novo — registra e retorna erro estruturado
        await audit_log.record(f"Payment failed for order {order_id}: {e}")
        raise  # ainda vai para dead letter queue
```

### Backoff Exponencial (SAQ backend)

```python
@task(queue="webhooks", retry=7)
async def dispatch_webhook(url: str, payload: dict) -> None:
    # Com SAQ, os retries usam backoff exponencial automático:
    # 1ª tentativa → imediata
    # 2ª → 30s depois
    # 3ª → 1min
    # 4ª → 2min
    # 5ª → 4min
    # etc.
    await http_client.post(url, json=payload)
```

---

## Comparação: Celery vs SAQ (Aura)

| Feature | Celery | SAQ (Aura) |
|---|---|---|
| Async nativo | ❌ (thread-pool) | ✅ (coroutines) |
| Latência | ~100ms | <5ms |
| Config necessária | ~20 variáveis | 1 URL |
| Acknowledge | Early (perde tasks) | Late (seguro) |
| Cron integrado | Celery Beat (processo separado) | ✅ nativo |
| Compartilha DI | ❌ | ✅ |
| Type hints | ❌ | ✅ |
| Dashboard | Flower (3rd party) | ✅ nativo |

# 🌌 Por que o Aura existe?

## O problema que nenhum framework resolveu direito

Em 2024-2025, o ecossistema Python web está preso em uma tensão fundamental:

- **Django** é "batteries included" — mas as baterias são de 2005.
- **FastAPI** é moderno — mas te deixa comprar todas as baterias separado.
- **Flask** é minimalista — mas a liberdade vira caos em projetos grandes.

O Aura nasceu para resolver **os problemas documentados de forma concreta**, não teórica.

---

## 🔥 Django — As dores reais

### 1. `settings.py` — O arquivo que não para de crescer

```python
# Tipico settings.py de produção
INSTALLED_APPS = ['django.contrib.admin', 'django.contrib.auth', ...]
DATABASES = {'default': {'ENGINE': '...', 'NAME': env('DB_NAME')}}
CELERY_BROKER_URL = env('REDIS_URL')
CELERY_RESULT_BACKEND = env('REDIS_URL')
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
# ... 200 linhas depois ...
```

**Problemas documentados:**
- Sem validação de tipos: `env('SECRET_KEY')` retorna string vazia sem erro
- Sem validação de startup: descobre que `DATABASE_URL` está errada em produção
- Sem modularização: configs de apps diferentes misturadas no mesmo arquivo
- Conflitos de merge em equipes: todo mundo edita o mesmo arquivo
- Cada projeto usa uma abordagem diferente (`django-environ`, `dynaconf`, `python-decouple`)

**Como Aura resolve:**

```toml
# aura.toml — separado por seção, type-safe
[app]
name = "Minha API"
secret_key = "${SECRET_KEY}"  # falha no startup se não existir

[database]
url = "${DATABASE_URL}"
pool_size = 10

[jobs]
backend = "saq"
broker = "${REDIS_URL}"
```

```python
# Acesso type-safe em qualquer lugar via DI
class UserService:
    def __init__(self, config: AuraConfig):
        self.db_url = config.database.url  # str, validado no startup
```

---

### 2. Django REST Framework — O maior gargalo de produtividade

O DRF tem um problema de design fundamental: o `ModelSerializer` faz coisas demais.

**Benchmark real (documentado pela comunidade):**
- Serializar 5.000 instâncias com `ModelSerializer`: **12,8 segundos**
- Serializar 5.000 instâncias com função Python simples: **0,034 segundos**
- **Diferença: 377x mais lento**

**Problemas estruturais do DRF:**

```python
# DRF: um Serializer que é validador, serializador E lógica de negócio
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email']

    def validate_email(self, value):
        # lógica de negócio aqui? no serializer? sério?
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email já usado")
        return value

    def create(self, validated_data):
        # e aqui a criação do objeto
        return User.objects.create(**validated_data)
```

**Problemas:**
- Validação e lógica de negócio misturadas
- N+1 queries por padrão (serializers aninhados sem `select_related`)
- Sem suporte async (ainda, em 2024)
- Respostas de erro inconsistentes entre endpoints
- `ViewSet` vs `GenericViewSet` vs `ReadOnlyModelViewSet` — confuso

**Como Aura resolve (separação clara de responsabilidades):**

```python
# Schema: só define a estrutura e validação (SDD)
class CreateUserSchema(Schema):
    name: str
    email: EmailStr

    @field_validator("email")
    def email_lowercase(cls, v: str) -> str:
        return v.lower()

# Service: só lógica de negócio
class UserService:
    async def create(self, data: CreateUserSchema) -> User:
        if await self.repo.exists(email=data.email):
            raise ConflictException("Email já usado")
        return await self.repo.create(**data.model_dump())

# Controller: só recebe e responde
class UserController:
    @post("/users")
    async def create_user(self, body: Body[CreateUserSchema]) -> UserResponseSchema:
        user = await self.service.create(body)
        return UserResponseSchema.model_validate(user)
```

---

### 3. ORM Síncrono em 2024

Django adicionou async views em 3.1 e async ORM em 4.1 — mas o ORM async do Django não é genuíno.

```python
# Django: async view mas ORM síncrono por baixo
async def get_user(request, user_id):
    # Isso bloqueia o event loop! O await é um wrapper de thread pool
    user = await sync_to_async(User.objects.get)(id=user_id)
    # Pior: acesso lazy bloqueia silenciosamente
    # user.profile  ← isso dispara uma query síncrona em contexto async!
    return JsonResponse(...)
```

**Como Aura resolve (SQLAlchemy 2.x genuinamente async):**

```python
# Aura: async real, sem wrappers
class UserRepository(Repository[User]):
    model = User

    async def get_with_profile(self, user_id: int) -> User:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.profile))  # eager loading explícito
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

---

### 4. Sistema de Tipos — A ilusão de segurança

```python
# Django: isso parece tipado, mas mypy chora
class UserViewSet(ModelViewSet):
    queryset = User.objects.all()  # QuerySet[User] — mas filter() não é tipado
    
user = User.objects.get(id=1)  # Pode lançar User.DoesNotExist — não está no tipo
users = User.objects.filter(active=True)  # QuerySet[User] mas sem inferência dos resultados
```

Django usa metaclass magic que quebra completamente análise estática. Um projeto que tentou migrar para mypy descreveu como "unsuccessful journey" — os tipos não funcionam com a infraestrutura mágica do Django.

**Como Aura resolve:**

```python
# Aura: tipos reais, sem magia
class UserRepository(Repository[User]):
    model = User

# Repository[User] → todos os métodos retornam User | None ou list[User]
# Pydantic v2 valida em runtime E é compreendido pelo mypy
user: User | None = await repo.get(1)        # tipo correto
users: list[User] = await repo.list(active=True)  # tipo correto
```

---

## ⚡ FastAPI — As dores reais

### 1. `Depends()` — DI amarrada ao ciclo HTTP

```python
# FastAPI: DI só funciona em rotas HTTP
async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2)):
    return ...

@router.get("/users/me")
async def me(user = Depends(get_current_user)):  # OK — dentro de uma rota
    return user

# Mas como usar o mesmo UserService em um job/task?
@celery.task
def send_email(user_id: int):
    # Depends() não existe aqui. Você precisa criar a sessão manualmente.
    db = SessionLocal()  # código duplicado!
    user = db.query(User).get(user_id)
    ...
```

**Como Aura resolve:**

```python
# Aura: DI funciona em qualquer contexto
@injectable
class EmailService:
    def __init__(self, config: AuraConfig, user_repo: UserRepository):
        self.config = config
        self.user_repo = user_repo

# Em uma rota HTTP — DI automática
class UserController:
    def __init__(self, email: EmailService):  # injetado automaticamente
        self.email = email

# Em um job/task — mesmo serviço, mesmo DI
@task(queue="emails")
async def send_welcome(user_id: int, email_svc: EmailService):  # injetado pelo worker
    user = await email_svc.user_repo.get(user_id)
    await email_svc.send_welcome(user)
```

### 2. Sem estrutura de projeto definida

FastAPI tem 82+ boilerplates diferentes no StarterIndex. Cada time inventa uma arquitetura. Em projetos grandes isso se torna um "messy catch-all" onde ninguém sabe onde colocar o quê.

**Como Aura resolve (estrutura opinionada mas extensível):**

```
meu_projeto/
├── aura.toml
├── main.py
├── modules/
│   ├── users/
│   │   ├── module.py      ← @Module(controllers, providers, exports)
│   │   ├── schema.py      ← DTOs (source of truth — SDD)
│   │   ├── service.py     ← lógica de negócio
│   │   ├── repository.py  ← acesso a dados
│   │   ├── tasks.py       ← background jobs
│   │   └── guards.py      ← auth guards do módulo
│   └── auth/
│       └── ...
└── shared/
    ├── models/            ← SQLAlchemy models
    └── middleware/
```

---

## 🔴 Celery — As dores reais

### 1. Sem suporte async nativo

```python
# Celery 5: ainda não suporta async def como tasks
@celery.task
def send_email(user_id: int):  # tem que ser síncrono
    # Para chamar código async, você precisa de:
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(send_email_async(user_id))  # gambiarra
```

**Como Aura resolve:**

```python
# Aura: async-first por design
@task(queue="emails", retry=3, timeout=30)
async def send_welcome_email(user_id: int, email: str) -> None:
    await smtp_client.send(email, template="welcome")

# Disparar:
await send_welcome_email.dispatch(user_id=1, email="user@example.com")
```

### 2. Tasks perdidas em crashes

Celery usa **acknowledge-early** por padrão: a task é removida da fila ANTES de ser processada. Se o worker crasha no meio, a task é perdida para sempre.

**Como Aura resolve:** SAQ usa **pessimistic execution** — a task permanece na fila até ser completada com sucesso. Se o worker crasha, ela é re-enfileirada automaticamente.

### 3. Rate limiting por worker, não global

```
# Celery: rate limit é POR WORKER, não global
# Se você tem 10 workers, cada um tem seu próprio rate limit
# Resultado: 10x mais requisições que o limite configurado
```

### 4. Monitoring inadequado

O Flower (monitor do Celery) não persiste dados — reiniciar o Flower apaga o histórico.

---

## 📊 Comparativo Rápido

| Feature | Django + DRF | FastAPI | **Aura** |
|---|---|---|---|
| Async genuíno | ❌ Wrapper | ✅ | ✅ |
| ORM async real | ❌ Thread pool | ❌ (manual) | ✅ SQLAlchemy 2.x |
| Type safety | ❌ Metaclass quebra | ✅ Parcial | ✅ Pydantic v2 strict |
| Jobs/Tasks nativo | ❌ Celery externo | ❌ Celery externo | ✅ SAQ / Taskiq |
| Estrutura de projeto | ⚠️ Apps (não escala) | ❌ Nenhuma | ✅ @Module NestJS-style |
| DI completo | ❌ Nenhum | ⚠️ Só em routes | ✅ Qualquer contexto |
| Config modular | ❌ settings.py | ⚠️ Manual | ✅ aura.toml + pydantic |
| OpenAPI auto | ❌ drf-spectacular | ✅ | ✅ |
| CLI / Scaffold | ⚠️ manage.py | ❌ | ✅ aura generate |
| N+1 query protection | ❌ | ❌ | ✅ Repository pattern |
| WebSockets | ⚠️ django-channels | ✅ Parcial | ✅ Nativo |
| SDD (Schema-Driven) | ❌ | ❌ | ✅ First-class |

---

## 🎯 Quem é o Aura para?

- Times que cresceram além do Django mas não querem abrir mão de estrutura
- Projetos novos que querem async-first desde o início
- Developers que vieram do NestJS/Spring e sentem falta de DI real
- APIs que precisam de jobs/queues sem a complexidade do Celery
- Quem quer que **a IA entenda o código** — schemas explícitos são contexto para LLMs

---

## 📖 Fontes da pesquisa

Esta análise é baseada em dados reais de:
- JetBrains Django Developer Survey 2024/2025
- Reddit r/django, r/Python (threads "why I left Django", "Django pain points 2024")
- Hacker News: "Ask HN: What do I move on to from Django?"
- GitHub Issues: django/django, encode/django-rest-framework
- Benchmarks documentados: Haki Benita (DRF performance), DoorDash Engineering Blog (Celery)
- Artigos: "My unsuccessful journey migrating Django to mypy"

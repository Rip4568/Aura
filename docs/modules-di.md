# Módulos & Injeção de Dependência

## Por que um sistema de módulos?

O maior problema de escala no Django/FastAPI é a **ausência de estrutura imposta**. Num projeto com 50+ endpoints, você acaba com:

- `views.py` com 3000 linhas
- `utils.py` que virou uma gaveta de funções sem relação
- `signals.py` acoplando coisas que não deviam se conhecer
- Imports circulares em todo lugar
- Testes que dependem de estado global

O Aura resolve isso com um **sistema de módulos inspirado no NestJS**: cada feature é encapsulada num módulo com seus próprios providers, controllers, e regras de visibilidade. O que não é exportado, não existe fora do módulo.

---

## Anatomia de um Módulo

```python
from aura import Module
from .controller import UserController
from .service import UserService
from .repository import UserRepository

@Module(
    providers=[UserRepository, UserService],   # quem pode ser injetado
    controllers=[UserController],              # quem responde às rotas
    exports=[UserService],                     # quem pode ser injetado por outros módulos
    prefix="/users",                           # prefixo de URL para este módulo
    tags=["Users"],                            # tag OpenAPI
)
class UserModule:
    pass
```

### Parâmetros do `@Module`

| Parâmetro | Tipo | Descrição |
|---|---|---|
| `providers` | `list[type]` | Classes injetáveis disponíveis dentro do módulo |
| `controllers` | `list[type]` | Classes que contêm os route handlers |
| `imports` | `list[type]` | Outros módulos cujos `exports` ficam disponíveis aqui |
| `exports` | `list[type]` | Providers que outros módulos podem importar |
| `prefix` | `str` | Prefixo de URL aplicado a todos os controllers |
| `tags` | `list[str]` | Tags OpenAPI padrão para as rotas do módulo |
| `guards` | `list` | Guards aplicados a todas as rotas do módulo |

---

## Injeção de Dependência

### Marcando uma classe como injetável

```python
from aura import injectable, Lifetime

# Singleton (padrão) — uma instância por aplicação
@injectable
class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

# Scoped — uma instância por request HTTP
@injectable(lifetime=Lifetime.SCOPED)
class RequestContext:
    def __init__(self) -> None:
        self.user_id: int | None = None
        self.trace_id: str = uuid4().hex

# Transient — nova instância a cada resolução
@injectable(lifetime=Lifetime.TRANSIENT)
class EmailBuilder:
    def build(self, template: str, context: dict) -> str:
        ...
```

### Lifetimes

| Lifetime | Instâncias | Quando usar |
|---|---|---|
| `SINGLETON` | 1 por app | Services, Repositories, Configs |
| `SCOPED` | 1 por request | RequestContext, UnityOfWork, por-request cache |
| `TRANSIENT` | Nova a cada injeção | Builders, Factories, objetos leves |

### Resolução automática por tipo

O container resolve dependências automaticamente via **type hints do `__init__`**:

```python
@injectable
class OrderService:
    def __init__(
        self,
        order_repo: OrderRepository,      # ← resolvido automaticamente
        user_service: UserService,        # ← resolvido automaticamente
        email_tasks: EmailTaskDispatcher, # ← resolvido automaticamente
    ) -> None:
        self.repo = order_repo
        self.users = user_service
        self.email = email_tasks
```

Você não instancia nada manualmente — o container cuida de toda a árvore de dependências.

---

## Composição de Módulos

```python
# auth/module.py
@Module(
    providers=[JWTService, AuthService],
    controllers=[AuthController],
    exports=[AuthService],   # ← disponibiliza AuthService para quem importar AuthModule
    prefix="/auth",
)
class AuthModule:
    pass

# users/module.py
@Module(
    imports=[AuthModule],              # ← importa AuthModule
    providers=[UserRepository, UserService],
    controllers=[UserController],
    exports=[UserService],
    prefix="/users",
)
class UserModule:
    pass
    # UserService pode injetar AuthService porque UserModule importa AuthModule

# app/module.py — módulo raiz
@Module(
    imports=[AuthModule, UserModule, PostModule, NotificationModule],
)
class AppModule:
    pass

# main.py
app = Aura(modules=[AppModule])
```

### Regras de visibilidade

```
AuthModule
  providers: [JWTService, AuthService]
  exports:   [AuthService]          ← só AuthService é visível externamente

UserModule
  imports:   [AuthModule]           ← importou AuthModule
  providers: [UserRepository, UserService]
  
  Visível em UserModule:
    ✅ UserRepository   (provider local)
    ✅ UserService      (provider local)
    ✅ AuthService      (exportado por AuthModule)
    ❌ JWTService       (AuthModule não exportou)
```

---

## Usando o Container Diretamente

Em casos especiais (scripts, testes, jobs), você pode resolver manualmente:

```python
from aura.di.container import DIContainer

container = DIContainer()
container.register(UserService)
container.register(UserRepository)

# Resolve toda a árvore de dependências automaticamente
service = await container.resolve(UserService)
await service.do_something()

# Resolução opcional (não levanta exceção se não encontrado)
service = await container.resolve_optional(UserService)

# Registrar instância já criada
config = MyConfig(debug=True)
container.register_instance(MyConfig, config)

# Registrar factory customizada
container.register_factory(
    DatabaseSession,
    lambda: AsyncSession(engine),
    lifetime=Lifetime.SCOPED,
)
```

---

## Contexto de Injeção

### HTTP Request

Em controllers e services chamados via HTTP, o container cria automaticamente um **scope por request**:

```python
@injectable(lifetime=Lifetime.SCOPED)
class RequestLogger:
    def __init__(self) -> None:
        self.logs: list[str] = []
        self.request_id = uuid4().hex
    
    def log(self, msg: str) -> None:
        self.logs.append(msg)

# Cada request recebe sua própria instância de RequestLogger
class UserController:
    def __init__(self, logger: RequestLogger) -> None:
        self.logger = logger   # instância única neste request
```

### Background Jobs

```python
@task(queue="default")
async def process_data(record_id: int) -> None:
    # Em tasks, o container cria um scope independente por execução
    # DI funciona exatamente igual ao contexto HTTP
    container = get_task_container()
    service = await container.resolve(DataService)
    await service.process(record_id)
```

### CLI Commands

```python
# aura/cli/commands.py
import typer
from aura.di.container import DIContainer

@app.command()
async def seed_db() -> None:
    container = DIContainer()
    # registrar providers...
    service = await container.resolve(SeedService)
    await service.run()
    typer.echo("Database seeded!")
```

---

## Estrutura de Projeto Recomendada

```
my_api/
├── main.py                    # Aura(modules=[AppModule])
├── app/
│   └── module.py              # @Module(imports=[...todos...])
├── auth/
│   ├── __init__.py
│   ├── module.py              # @Module(...)
│   ├── controller.py          # @post("/login"), @post("/register")
│   ├── service.py             # @injectable — lógica de autenticação
│   ├── repository.py          # Repository[User]
│   ├── schemas.py             # LoginDTO, TokenResponse
│   ├── guards.py              # JWTGuard
│   └── tasks/
│       └── email_tasks.py     # @task(queue="emails")
├── users/
│   ├── module.py
│   ├── controller.py
│   ├── service.py
│   ├── repository.py
│   └── schemas.py
└── posts/
    ├── module.py
    ├── controller.py
    ├── service.py
    └── ...
```

Cada pasta é uma **vertical slice** — contém tudo o que aquela feature precisa. Sem `utils/` gigantes, sem `views.py` de 3000 linhas.

---

## Guards — Autorização por Módulo, Controller ou Rota

```python
from aura import Guard
from starlette.requests import Request

class JWTGuard(Guard):
    async def can_activate(self, request: Request) -> bool:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            return False
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.state.user = payload
            return True
        except jwt.InvalidTokenError:
            return False

# Guard no módulo inteiro
@Module(
    guards=[JWTGuard],      # ← aplica em todas as rotas do módulo
    controllers=[UserController],
    ...
)
class UserModule:
    pass

# Guard em controller específico
@post("/admin/users", guards=[AdminGuard, JWTGuard])
async def create_admin_user(body: Annotated[CreateUserDTO, Body()]) -> UserResponse:
    ...

# Guard global (toda a aplicação)
app = Aura(
    modules=[AppModule],
    guards=[RateLimitGuard],  # ← aplica em absolutamente todas as rotas
)
```

---

## Exemplo Completo: Feature de Auth do Zero

```python
# auth/schemas.py
from aura import Schema

class LoginDTO(Schema):
    email: str
    password: str

class RegisterDTO(Schema):
    name: str
    email: str
    password: str

class TokenResponse(Schema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

# auth/service.py
from aura import injectable
from aura import UnauthorizedException, ConflictException

@injectable
class AuthService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.repo = user_repo

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self.repo.first(email=email)
        if not user or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Invalid credentials")
        
        token = create_jwt(user.id, expires_in=3600)
        return TokenResponse(access_token=token, expires_in=3600)

    async def register(self, data: RegisterDTO) -> UserResponse:
        if await self.repo.exists(email=data.email):
            raise ConflictException(f"Email {data.email} already registered")
        
        user = await self.repo.create(
            name=data.name,
            email=data.email,
            hashed_password=hash_password(data.password),
        )
        return UserResponse.model_validate(user, from_attributes=True)

# auth/controller.py
from aura import post, Body
from typing import Annotated

class AuthController:
    def __init__(self, service: AuthService) -> None:
        self.service = service

    @post("/login")
    async def login(self, body: Annotated[LoginDTO, Body()]) -> TokenResponse:
        return await self.service.login(body.email, body.password)

    @post("/register", status=201)
    async def register(self, body: Annotated[RegisterDTO, Body()]) -> UserResponse:
        return await self.service.register(body)

# auth/module.py
from aura import Module

@Module(
    providers=[AuthService, UserRepository],
    controllers=[AuthController],
    exports=[AuthService],
    prefix="/auth",
    tags=["Auth"],
)
class AuthModule:
    pass
```

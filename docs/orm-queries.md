# ORM & Queries — Repository Pattern

## Visão Geral

O Aura usa **SQLAlchemy 2.x async** como ORM — o único ORM Python com suporte nativo real a async (não é thread-pool como o Django ORM). Por cima do SQLAlchemy, o Aura oferece o `Repository[T]`, um padrão genérico que elimina 80% do código boilerplate de acesso a dados.

```
Controller → Service → Repository[Model] → AsyncSession → PostgreSQL/SQLite/...
```

---

## Definindo um Model

```python
from aura.orm import AuraModel, CharField, EmailField, BooleanField, relationship
from sqlalchemy.orm import Mapped

class User(AuraModel):
    __tablename__ = "users"

    name:    Mapped[str]  = CharField(max_length=100)
    email:   Mapped[str]  = EmailField(max_length=200, unique=True, index=True)
    active:  Mapped[bool] = BooleanField(default=True)

    # Relacionamento
    posts:   Mapped[list["Post"]] = relationship("Post", back_populates="author")
```

### O que `AuraModel` fornece automaticamente

```python
# aura/orm/base.py — incluído em todo model
class AuraModel(DeclarativeBase):
    id:         Mapped[int]      # PK auto-increment
    created_at: Mapped[datetime] # preenchido no INSERT
    updated_at: Mapped[datetime] # atualizado em todo UPDATE
    
    def to_dict(self) -> dict:   # serialização básica
        ...
```

---

## Criando um Repository

```python
from aura.orm.repository import Repository
from .models import User

class UserRepository(Repository[User]):
    model = User  # ← única linha necessária
```

Pronto. Você tem todos os métodos CRUD prontos.

---

## Operações CRUD

### Buscar por ID

```python
# Retorna User | None
user = await repo.get(42)

# Retorna User ou levanta NotFoundException (404)
user = await repo.get_or_raise(42)
```

### Listar com paginação e filtros

```python
# Todos os usuários (padrão: limit=100, offset=0)
users = await repo.list()

# Com paginação
users = await repo.list(limit=20, offset=40)  # página 3

# Filtros por igualdade (coluna=valor)
users = await repo.list(active=True)
users = await repo.list(active=True, role="admin")

# Ordenação
users = await repo.list(order_by="name")
users = await repo.list(order_by="created_at", active=True, limit=10)
```

### Criar

```python
user = await repo.create(
    name="João Silva",
    email="joao@example.com",
    active=True,
)
# user.id, user.created_at, user.updated_at são preenchidos automaticamente
```

### Atualizar

```python
# Só os campos passados são alterados
user = await repo.update(42, name="João Atualizado", active=False)
# Levanta NotFoundException se id=42 não existir
```

### Deletar

```python
deleted = await repo.delete(42)  # True se deletou, False se não encontrou
```

### Verificar existência

```python
exists = await repo.exists(email="joao@example.com")
# True ou False
```

### Contar registros

```python
total = await repo.count()                    # total de usuários
ativos = await repo.count(active=True)        # apenas ativos
admins = await repo.count(role="admin")
```

### Primeiro resultado

```python
user = await repo.first(email="joao@example.com")
# User | None — útil para busca por campo único
```

### Inserção em lote

```python
users = await repo.bulk_create([
    {"name": "Alice", "email": "alice@example.com"},
    {"name": "Bob",   "email": "bob@example.com"},
    {"name": "Carol", "email": "carol@example.com"},
])
# Retorna lista de User com ids e timestamps preenchidos
```

---

## Integrando com Service e Controller

```python
# schemas.py
from aura import Schema

class CreateUserDTO(Schema):
    name:  str
    email: str

class UserResponse(Schema):
    id:         int
    name:       str
    email:      str
    active:     bool
    created_at: datetime

# repository.py
from aura.orm.repository import Repository
from .models import User

class UserRepository(Repository[User]):
    model = User

# service.py
from aura import injectable
from sqlalchemy.ext.asyncio import AsyncSession
from .repository import UserRepository
from .schemas import CreateUserDTO, UserResponse

@injectable
class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = UserRepository(session)

    async def list_users(self, page: int = 1, page_size: int = 20) -> list[User]:
        # Retorna a lista contendo objetos ORM diretamente
        offset = (page - 1) * page_size
        return await self.repo.list(limit=page_size, offset=offset, active=True)

    async def get_user(self, user_id: int) -> User:
        # Retorna o objeto ORM diretamente — NotFoundException (404) disparada automaticamente se não existir
        return await self.repo.get_or_raise(user_id)

    async def create_user(self, data: CreateUserDTO) -> User:
        # Verificar duplicata antes de criar
        if await self.repo.exists(email=data.email):
            from aura import ConflictException
            raise ConflictException(f"Email {data.email} already in use")
        
        return await self.repo.create(**data.model_dump())

    async def update_user(self, user_id: int, data: dict) -> User:
        return await self.repo.update(user_id, **data)

    async def delete_user(self, user_id: int) -> None:
        deleted = await self.repo.delete(user_id)
        if not deleted:
            from aura import NotFoundException
            raise NotFoundException(f"User {user_id} not found")

# controller.py
from aura import get, post, put, delete, Body
from .service import UserService
from .schemas import CreateUserDTO, UserResponse

class UserController:
    def __init__(self, service: UserService) -> None:
        self.service = service

    @get("/users")
    async def list_users(self) -> list[UserResponse]:
        # O Aura serializa list[User] para list[UserResponse] de forma ultra-rápida via TypeAdapter!
        return await self.service.list_users()

    @get("/users/{id}")
    async def get_user(self, id: int) -> UserResponse:
        # 'id' é inferido automaticamente como path parameter a partir da rota
        return await self.service.get_user(id)

    @post("/users", status=201)
    async def create_user(self, body: Body[CreateUserDTO]) -> UserResponse:
        return await self.service.create_user(body)

    @delete("/users/{id}", status=204)
    async def delete_user(self, id: int) -> None:
        await self.service.delete_user(id)

```

---

## Queries Avançadas com AuraQL e SQLAlchemy

O `Repository` do Aura e o manager `.objects` (AuraQL) cobrem a grande maioria dos casos de forma limpa. Para queries customizadas ou relações de eager loading, o AuraQL fornece uma interface fluente estilo Django. Caso precise de controle total de baixo nível, você também pode usar o SQLAlchemy `select()` ou SQL puro.

```python
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload
from aura.orm import Q

class UserRepository(Repository[User]):
    model = User

    # 1. Recomendado: Query fluente e expressiva com AuraQL
    async def search(
        self,
        query: str,
        active: bool = True,
        role: str | None = None,
    ) -> list[User]:
        # Suporta Q objects para queries complexas com OR
        qs = User.objects.filter(
            Q(name__icontains=query) | Q(email__icontains=query),
            active=active,
        )
        if role:
            qs = qs.filter(role=role)
        return await qs.all()

    # 2. Eager loading simplificado de relacionamentos (evita N+1)
    async def get_with_posts(self, user_id: int) -> User | None:
        return await (
            User.objects
            .include("posts")  # Eager loading nativo estilo Django/Prisma
            .get_or_none(id=user_id)
        )

    # Agregações
    async def stats(self) -> dict:
        stmt = select(
            func.count(User.id).label("total"),
            func.count(User.id).filter(User.active == True).label("active"),
        )
        result = await self.session.execute(stmt)
        row = result.one()
        return {"total": row.total, "active": row.active}

    # Raw SQL quando necessário
    async def find_by_raw(self, email_domain: str) -> list[User]:
        stmt = text("SELECT * FROM users WHERE email LIKE :pattern")
        result = await self.session.execute(stmt, {"pattern": f"%@{email_domain}"})
        return list(result.mappings().all())
```

---

## Paginação com Metadados

```python
from dataclasses import dataclass

@dataclass
class Page[T]:
    items: list[T]
    total: int
    page: int
    page_size: int
    
    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

class UserRepository(Repository[User]):
    model = User

    async def paginate(
        self,
        page: int = 1,
        page_size: int = 20,
        **filters,
    ) -> Page[User]:
        offset = (page - 1) * page_size
        items = await self.list(limit=page_size, offset=offset, **filters)
        total = await self.count(**filters)
        return Page(items=items, total=total, page=page, page_size=page_size)
```

---

## Consultas Paralelas (Concorrentes)

Assim como o `Promise.all` no NodeJS, você pode querer disparar múltiplas buscas ou atualizações no banco de dados de forma paralela para otimizar o tempo de resposta do servidor.

No entanto, **o SQLAlchemy impede consultas concorrentes usando a MESMA sessão/conexão** (disparando erros de concorrência ou de estado inválido caso você tente usar `asyncio.gather` com o mesmo objeto de sessão).

Para contornar isso e fornecer a melhor DX possível, o Aura oferece o helper `db.parallel`. Ele recebe uma lista de funções executáveis, abre sessões e conexões independentes de forma assíncrona diretamente a partir do pool, executa-as em paralelo de forma transparente e retorna os resultados na ordem especificada:

### Exemplo de uso:

```python
async def get_dashboard_data(self) -> dict:
    # Executa ambas as buscas em paralelo usando o pool de conexões de forma segura
    recent_users, total_users = await db.parallel(
        lambda s: UserRepository(s).list(limit=5, order_by="created_at"),
        lambda s: UserRepository(s).count()
    )
    return {
        "users": recent_users,
        "total": total_users
    }
```

---


## Configurando o Banco de Dados

```python
# config .env
AURA__DATABASE__URL=postgresql+asyncpg://user:pass@localhost/mydb
# ou para SQLite em dev:
AURA__DATABASE__URL=sqlite+aiosqlite:///./dev.db

# main.py
from aura import Aura
from aura.orm.session import db

app = Aura(modules=[UserModule], title="My API")

# Inicializar o banco na startup
@app.on_startup  # (feature planejada — ver roadmap)
async def setup_db():
    await db.init(app.config.database.url)
```

### Migrações com Alembic

```bash
# Criar migration
aura migrate make "create users table"

# Aplicar migrations
aura migrate up

# Reverter
aura migrate down
```

---

## ORM vs Raw SQL — Quando usar cada um

| Situação | Use |
|---|---|
| CRUD simples | `Repository[T]` |
| Filtros e paginação | `repo.list(**filters)` |
| Query com JOIN | SQLAlchemy direto |
| Full-text search | SQLAlchemy + extensão DB |
| Analytics / relatórios complexos | Raw SQL via `text()` |
| Migrations | Alembic (`aura migrate`) |

---

## Drivers Suportados

| Banco | Driver async | Install |
|---|---|---|
| PostgreSQL | `asyncpg` | `pip install asyncpg` |
| SQLite | `aiosqlite` | `pip install aiosqlite` |
| MySQL | `aiomysql` | `pip install aiomysql` |
| SQL Server | `aioodbc` | `pip install aioodbc` |

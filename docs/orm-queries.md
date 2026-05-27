# ORM & Queries — Repository Pattern

## Visão Geral

O Aura usa **SQLAlchemy 2.x async** como ORM — o único ORM Python com suporte nativo real a async (não é thread-pool como o Django ORM). Por cima do SQLAlchemy, o Aura oferece o `Repository[T]`, um padrão genérico que elimina 80% do código boilerplate de acesso a dados.

```
Controller → Service → Repository[Model] → AsyncSession → PostgreSQL/SQLite/...
```

---

## Definindo um Model

```python
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from aura.orm.base import AuraModel

class User(AuraModel):
    __tablename__ = "users"

    name:    Mapped[str]  = mapped_column(String(100))
    email:   Mapped[str]  = mapped_column(String(200), unique=True, index=True)
    active:  Mapped[bool] = mapped_column(Boolean, default=True)

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

    async def list_users(self, page: int = 1, page_size: int = 20) -> list[UserResponse]:
        offset = (page - 1) * page_size
        users = await self.repo.list(limit=page_size, offset=offset, active=True)
        return [UserResponse.model_validate(u, from_attributes=True) for u in users]

    async def get_user(self, user_id: int) -> UserResponse:
        user = await self.repo.get_or_raise(user_id)  # 404 automático
        return UserResponse.model_validate(user, from_attributes=True)

    async def create_user(self, data: CreateUserDTO) -> UserResponse:
        # Verificar duplicata antes de criar
        if await self.repo.exists(email=data.email):
            from aura import ConflictException
            raise ConflictException(f"Email {data.email} already in use")
        
        user = await self.repo.create(**data.model_dump())
        return UserResponse.model_validate(user, from_attributes=True)

    async def update_user(self, user_id: int, data: dict) -> UserResponse:
        user = await self.repo.update(user_id, **data)
        return UserResponse.model_validate(user, from_attributes=True)

    async def delete_user(self, user_id: int) -> None:
        deleted = await self.repo.delete(user_id)
        if not deleted:
            from aura import NotFoundException
            raise NotFoundException(f"User {user_id} not found")

# controller.py
from aura import get, post, put, delete, Param, Body
from typing import Annotated
from .service import UserService
from .schemas import CreateUserDTO, UserResponse

class UserController:
    def __init__(self, service: UserService) -> None:
        self.service = service

    @get("/users")
    async def list_users(self) -> list[UserResponse]:
        return await self.service.list_users()

    @get("/users/{id}")
    async def get_user(
        self,
        id: Annotated[int, Param()],
    ) -> UserResponse:
        return await self.service.get_user(id)

    @post("/users", status=201)
    async def create_user(
        self,
        body: Annotated[CreateUserDTO, Body()],
    ) -> UserResponse:
        return await self.service.create_user(body)

    @delete("/users/{id}", status=204)
    async def delete_user(
        self,
        id: Annotated[int, Param()],
    ) -> None:
        await self.service.delete_user(id)
```

---

## Queries Avançadas com SQLAlchemy Direto

O `Repository` cobre 80% dos casos. Para queries complexas, acesse o `session` diretamente:

```python
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload, joinedload

class UserRepository(Repository[User]):
    model = User

    # Query customizada com JOIN e filtros complexos
    async def search(
        self,
        query: str,
        active: bool = True,
        role: str | None = None,
    ) -> list[User]:
        stmt = (
            select(User)
            .where(
                and_(
                    User.active == active,
                    or_(
                        User.name.ilike(f"%{query}%"),
                        User.email.ilike(f"%{query}%"),
                    )
                )
            )
        )
        if role:
            stmt = stmt.where(User.role == role)
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # Eager loading de relacionamentos (evita N+1)
    async def get_with_posts(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.posts))  # carrega posts em 1 query
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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

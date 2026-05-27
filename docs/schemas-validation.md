# 📋 Schemas e Validação de Dados

O Aura usa **Pydantic v2** como sistema de validação em todo o framework. Schemas (DTOs) são a **fonte da verdade** — a definição de um schema é o que gera validação, documentação OpenAPI e type safety simultaneamente.

---

## O que é um Schema (DTO)?

Um **Schema** em Aura é uma classe Pydantic que define a estrutura de dados para:

- **Request body** — o que o cliente envia
- **Response** — o que a API devolve
- **Query params** — parâmetros de URL tipados
- **Configuração** — módulos que recebem config type-safe

> **SDD — Schema-Driven Development:** você escreve o schema antes do código. O framework deriva validação, serialização e documentação a partir dele.

---

## Schema base

```python
from aura import Schema

class CreateUserSchema(Schema):
    name: str
    email: str
```

`Schema` herda de `pydantic.BaseModel` com configurações sensatas já definidas:

| Configuração | Valor | Efeito |
|---|---|---|
| `from_attributes` | `True` | Permite criar schema a partir de objeto ORM: `Schema.model_validate(user)` |
| `populate_by_name` | `True` | Aceita tanto o nome do campo quanto o alias |
| `str_strip_whitespace` | `True` | Remove espaços no início/fim de strings automaticamente |

---

## Tipos suportados

Pydantic v2 aceita todos os tipos Python nativos e muitos extras:

```python
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
from pydantic import EmailStr, HttpUrl, AnyUrl, field_validator, model_validator

class CreateProductSchema(Schema):
    # Tipos primitivos
    name: str
    description: str | None = None     # opcional, default None
    price: Decimal
    stock: int = 0                      # default 0
    active: bool = True
    
    # Tipos ricos
    email: EmailStr                     # valida formato de email
    website: HttpUrl | None = None      # valida URL completa
    sku: UUID                           # UUID v4
    
    # Datas
    launch_date: date
    created_at: datetime | None = None
    
    # Listas e dicionários
    tags: list[str] = []
    metadata: dict[str, str] = {}
    
    # Enum
    category: Literal["electronics", "clothing", "food"]
    status: ProductStatus              # Enum Python nativo
```

---

## Validadores de campo

```python
from pydantic import field_validator, Field

class CreateUserSchema(Schema):
    name: str = Field(min_length=2, max_length=100, description="Nome completo")
    email: EmailStr
    password: str = Field(min_length=8)
    age: int = Field(ge=0, le=150)      # 0 <= age <= 150
    bio: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def name_must_have_space(cls, v: str) -> str:
        if " " not in v.strip():
            raise ValueError("Nome deve conter nome e sobrenome")
        return v.strip().title()  # "JOÃO SILVA" → "João Silva"

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Senha deve ter pelo menos uma letra maiúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve ter pelo menos um número")
        return v
```

---

## Validadores de modelo (cross-field)

Quando a validação precisa verificar múltiplos campos ao mesmo tempo:

```python
from pydantic import model_validator

class DateRangeSchema(Schema):
    start_date: date
    end_date: date
    
    @model_validator(mode="after")
    def end_after_start(self) -> "DateRangeSchema":
        if self.end_date <= self.start_date:
            raise ValueError("end_date deve ser posterior a start_date")
        return self

class PasswordChangeSchema(Schema):
    new_password: str = Field(min_length=8)
    confirm_password: str
    
    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeSchema":
        if self.new_password != self.confirm_password:
            raise ValueError("Senhas não coincidem")
        return self
```

---

## Schemas de Request vs Response

É uma boa prática separar o schema de entrada do schema de saída:

```python
# O que o cliente envia (não inclui id, timestamps)
class CreateUserSchema(Schema):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)

# O que o cliente recebe (nunca expõe password)
class UserResponseSchema(Schema):
    id: int
    name: str
    email: str
    created_at: datetime
    
    # from_attributes=True (herdado de Schema) permite isso:
    # UserResponseSchema.model_validate(user_orm_object)

# Para updates parciais (todos os campos opcionais)
class UpdateUserSchema(Schema):
    name: str | None = None
    email: EmailStr | None = None
```

---

## Schemas aninhados

```python
class AddressSchema(Schema):
    street: str
    city: str
    state: str = Field(min_length=2, max_length=2)  # UF
    zip_code: str = Field(pattern=r"^\d{5}-?\d{3}$")

class CreateCustomerSchema(Schema):
    name: str
    email: EmailStr
    address: AddressSchema                    # schema aninhado
    secondary_addresses: list[AddressSchema] = []

# Uso:
data = {
    "name": "Alice",
    "email": "alice@example.com",
    "address": {
        "street": "Rua das Flores, 123",
        "city": "São Paulo",
        "state": "SP",
        "zip_code": "01310-100"
    }
}
schema = CreateCustomerSchema.model_validate(data)
# Valida recursivamente — erros em address.state também são capturados
```

---

## Como a validação funciona no pipeline

Quando o cliente envia um request com body JSON:

```
POST /users
Content-Type: application/json

{
    "name": "  alice  ",
    "email": "ALICE@EXAMPLE.COM",
    "password": "fraca"
}
```

**O que acontece internamente:**

```
1. Router recebe o request
2. Identifica Body[CreateUserSchema] na assinatura do handler
3. Lê o JSON: {"name": "  alice  ", "email": "ALICE@EXAMPLE.COM", "password": "fraca"}
4. Chama CreateUserSchema.model_validate(data)
5. Pydantic executa:
   a. str_strip_whitespace → name = "alice"
   b. @field_validator("email") → email = "alice@example.com"
   c. @field_validator("password") → ValueError: "Senha deve ter pelo menos uma letra maiúscula"
6. ValidationError é capturado pelo router
7. Retorna 422 Unprocessable Entity:
```

```json
{
    "detail": [
        {
            "loc": ["password"],
            "msg": "Value error, Senha deve ter pelo menos uma letra maiúscula",
            "type": "value_error"
        }
    ]
}
```

---

## Usando schemas no controller

```python
from aura.routing.params import Body, Query, Param, Header

class UserController:
    
    @post("/users")
    async def create_user(
        self,
        body: Body[CreateUserSchema],   # valida o JSON body
    ) -> UserResponseSchema:
        user = await self.service.create(body)
        return UserResponseSchema.model_validate(user)

    @get("/users")
    async def list_users(
        self,
        page: Query[int] = 1,           # ?page=1 — converte string para int
        limit: Query[int] = 20,          # ?limit=20
        search: Query[str | None] = None,  # ?search=alice — opcional
    ) -> list[UserResponseSchema]:
        return await self.service.list(page=page, limit=limit, search=search)

    @get("/users/{user_id}")
    async def get_user(
        self,
        user_id: Param[int],            # /users/42 — converte "42" para int
    ) -> UserResponseSchema:
        user = await self.service.get(user_id)
        return UserResponseSchema.model_validate(user)
    
    @put("/users/{user_id}")
    async def update_user(
        self,
        user_id: Param[int],
        body: Body[UpdateUserSchema],
        auth: Header[str],              # Authorization header
    ) -> UserResponseSchema:
        user = await self.service.update(user_id, body)
        return UserResponseSchema.model_validate(user)
```

---

## Convertendo ORM → Schema

```python
# ORM model (SQLAlchemy)
class User(AuraModel):
    __tablename__ = "users"
    name: Mapped[str]
    email: Mapped[str]

# Schema de resposta
class UserResponseSchema(Schema):
    id: int
    name: str
    email: str
    created_at: datetime

# Conversão — funciona graças a from_attributes=True
user: User = await repo.get(1)
response: UserResponseSchema = UserResponseSchema.model_validate(user)
# ↑ lê os atributos do objeto ORM diretamente

# Serialização para JSON
json_data: dict = response.model_dump(mode="json")
# {
#   "id": 1,
#   "name": "Alice",
#   "email": "alice@example.com",
#   "created_at": "2024-01-15T10:30:00Z"
# }
```

---

## ResponseSchema — para respostas padronizadas

```python
from aura import Schema, ResponseSchema

# Schema simples
class UserSchema(Schema):
    id: int
    name: str
    email: str

# Para listas paginadas — padrão consistente para toda a API
class PaginatedResponseSchema(ResponseSchema):
    items: list[UserSchema]
    total: int
    page: int
    pages: int
    
# Uso no controller
@get("/users")
async def list_users(self, page: Query[int] = 1) -> PaginatedResponseSchema:
    users, total = await self.service.list_paginated(page=page)
    return PaginatedResponseSchema(
        items=[UserSchema.model_validate(u) for u in users],
        total=total,
        page=page,
        pages=(total + 19) // 20,
    )
```

---

## OpenAPI auto-gerado dos schemas

Todo schema definido é automaticamente incluído no `/openapi.json`:

```python
class CreateProductSchema(Schema):
    """Dados para criação de um produto."""  # ← vira description no OpenAPI
    
    name: str = Field(description="Nome do produto", example="Notebook Dell")
    price: Decimal = Field(description="Preço em R$", example="2999.90")
    category: str = Field(description="Categoria", example="electronics")
```

Resultado no `/docs`:
- Formulário interativo com todos os campos
- Exemplos pré-preenchidos
- Validações documentadas (min_length, pattern, etc.)
- Tipos corretos (string, number, boolean, array, object)

---

## Boas práticas

```python
# ✅ Separe schemas por responsabilidade
class CreateUserSchema(Schema): ...      # entrada (POST)
class UpdateUserSchema(Schema): ...      # atualização parcial (PATCH/PUT)
class UserResponseSchema(Schema): ...    # saída (GET)
class UserListItemSchema(Schema): ...    # item em listagem (menor que ResponseSchema)

# ✅ Nunca exponha campos sensíveis no ResponseSchema
class UserResponseSchema(Schema):
    id: int
    name: str
    email: str
    # ← password, password_hash, secret_token: NUNCA aqui

# ✅ Use Field() para documentar campos
name: str = Field(description="Nome completo", min_length=2, max_length=100)

# ✅ Valide no schema, não no service
@field_validator("cpf")
def validate_cpf(cls, v: str) -> str:
    if not is_valid_cpf(v):
        raise ValueError("CPF inválido")
    return v

# ✅ Use Literal para enums simples
status: Literal["active", "inactive", "pending"] = "active"

# ✅ Use Enum para enums com lógica
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"

role: UserRole = UserRole.USER
```

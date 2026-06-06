# SDD — Spec-Driven Development

## O que é

**Spec-Driven Development** é a metodologia central do Aura: você escreve a **especificação** antes do código, e essa spec se torna a fonte de verdade de todo o sistema.

A spec define:
- **O contrato da API** — quais endpoints existem, o que aceitam, o que retornam
- **As regras de negócio** — validações, restrições, tipos
- **A documentação** — gerada automaticamente, nunca desincroniza do código

A IA (Claude, GPT, Copilot, etc.) lê a spec e **implementa, verifica, e corrige** com precisão — porque a spec é formal, sem ambiguidade.

---

## Por que SDD importa para desenvolvimento com IA

O problema do desenvolvimento orientado a IA hoje é a **imprecisão**: você descreve o que quer em linguagem natural, a IA tenta adivinhar, e você passa metade do tempo corrigindo o que foi gerado errado.

SDD inverte isso: **a spec é precisa**, a IA não precisa adivinhar nada.

```
Sem SDD:
  Você: "crie um endpoint de usuário com validações"
  IA: gera algo, você corrige, ela regera, você corrige de novo...

Com SDD:
  Você: escreve a spec (schema + contrato)
  IA: lê a spec formal, implementa exatamente o que foi especificado
  Resultado: correto na primeira vez
```

---

## Como funciona no Aura

A spec no Aura é composta de:

### 1. Schemas — o contrato de dados

```python
from aura import Schema
from pydantic import EmailStr, field_validator

class CreateUserSpec(Schema):
    """Spec para criação de usuário.
    
    Regras:
    - name: obrigatório, 2-100 chars
    - email: formato válido, normalizado para minúsculas
    - age: opcional, entre 18 e 120
    """
    name:  str
    email: EmailStr
    age:   int | None = None

    @field_validator("name")
    def name_length(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @field_validator("email")
    def normalize_email(cls, v: str) -> str:
        return v.lower()

    @field_validator("age")
    def valid_age(cls, v: int | None) -> int | None:
        if v is not None and not (18 <= v <= 120):
            raise ValueError("Age must be between 18 and 120")
        return v
```

Essa spec é:
- ✅ **Executável** — o framework usa ela para validar requests
- ✅ **Documentável** — OpenAPI gerado automaticamente a partir dela
- ✅ **Legível por IA** — clara o suficiente para gerar a implementação

### 2. Route decorators — o contrato de endpoint

```python
@post("/users", status=201, response=UserResponse)
async def create_user(body: Annotated[CreateUserSpec, Body()]) -> UserResponse:
    ...
```

A assinatura da função é a spec do endpoint: método, path, status code, entrada, saída. Tudo tipado, tudo explícito.

### 3. OpenAPI — a spec publicada

O Aura gera o OpenAPI 3.1 automaticamente a partir dos schemas e decorators:

```
GET /openapi.json  →  spec completa e sempre atualizada
GET /docs          →  Swagger UI interativo
GET /redoc         →  Redoc legível
```

Você pode copiar o `/openapi.json` e dar pra uma IA gerar um client SDK, testes de integração, ou implementar novos endpoints seguindo o mesmo padrão.

---

## O fluxo SDD no dia a dia

```
1. Escrever a spec (Schema + decorator)
         ↓
2. IA lê a spec e implementa o service/repository
         ↓
3. Framework valida requests contra a spec automaticamente
         ↓
4. OpenAPI gerado automaticamente, sempre sincronizado
         ↓
5. Testes gerados a partir da spec (validam o contrato)
         ↓
6. Client SDKs gerados a partir da spec (frontend, mobile)
```

---

## Comparação: sem spec vs com spec

### Sem SDD (Django/Flask tradicional)

```python
# Você descreve em linguagem natural para a IA:
# "crie um endpoint POST /users que aceita nome e email,
#  valida que o email é único e retorna o usuário criado"

# A IA gera algo como:
@app.route("/users", methods=["POST"])
def create_user():
    data = request.get_json()
    # IA adivinhou que você quer email único — talvez certo, talvez não
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "exists"}), 400
    # Sem validação de tipos, sem formato de erro consistente
    user = User(name=data["name"], email=data["email"])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201
```

Problemas:
- ❌ A IA "adivinhou" o comportamento de unicidade
- ❌ Sem validação de tipo/formato
- ❌ Formato de erro inconsistente
- ❌ Documentação: inexistente

### Com SDD (Aura)

```python
# Você escreve a spec primeiro — precisa, sem ambiguidade:

class CreateUserSpec(Schema):
    name:  str          # obrigatório
    email: EmailStr     # formato validado automaticamente

class UserResponse(Schema):
    id:         int
    name:       str
    email:      str
    created_at: datetime

# A IA lê a spec e implementa o service:

@injectable
class UserService:
    async def create(self, data: CreateUserSpec) -> UserResponse:
        if await self.repo.exists(email=data.email):
            raise ConflictException(f"Email {data.email} already in use")
        user = await self.repo.create(**data.model_dump())
        return UserResponse.model_validate(user, from_attributes=True)

# O controller é trivial — a spec já define tudo:

@post("/users", status=201)
async def create_user(body: Annotated[CreateUserSpec, Body()]) -> UserResponse:
    return await self.service.create(body)
```

Resultado:
- ✅ Validação automática (email inválido → 422 com detalhe)
- ✅ Formato de erro consistente em toda a API
- ✅ OpenAPI gerado, sempre correto
- ✅ A IA implementou exatamente o que estava na spec

---

## SDD como linguagem entre você e a IA

A spec é a **linguagem comum** entre você (humano), a IA (assistente), e o framework (executor):

```
Você pensa:   "quero um endpoint que cria usuário"
Você escreve: CreateUserSpec + @post("/users")   ← spec formal
IA lê:        a spec tipada e sem ambiguidade
IA gera:      service, repository, testes — todos corretos
Framework:    valida, documenta, serializa automaticamente
```

É o que torna o Aura especialmente adequado para desenvolvimento assistido por IA: **quanto mais formal a spec, menos o modelo precisa adivinhar, menos você precisa corrigir.**

---

## Docs relacionados

- [Schemas & Validação](schemas-validation.md) — como escrever specs no Aura
- [ORM & Queries](orm-queries.md) — Repository[T] como spec de acesso a dados
- [Módulos & DI](modules-di.md) — @Module como spec de arquitetura
- [Roadmap](roadmap.md) — geração de código a partir de specs (em desenvolvimento)

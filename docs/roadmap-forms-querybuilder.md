# Roadmap: Aura Forms + AuraQL Query Builder

> **Status:** Planejamento — não implementar sem revisão do Arquiteto.  
> **Horizonte:** v0.5.0 / v0.6.0  
> **Autor:** Claude Code (líder) — sessão 2026-05-28  
> **Motivação:** Transformar o Aura em um framework de produção capaz de competir com Django em produtividade, mantendo a filosofia async-first e type-safe.

---

## Visão Geral

Dois sistemas independentes, mas que se complementam:

| Sistema | O que resolve | Paralelo com |
|---|---|---|
| **Aura Forms** | Validação de input, carregamento de relacionamentos, renderização HTML | Django Forms + WTForms |
| **AuraQL** | Query builder fluente, type-safe, com eager loading declarativo | Django ORM QuerySet + Prisma |

Juntos, eles eliminam as duas maiores dores de produtividade do Aura hoje:
1. Validação de formulários exige boilerplate manual (Pydantic Schema + validação DB separados)
2. Queries com relacionamentos exigem SQLAlchemy direto — sem abstração de alto nível

---

## Parte 1 — Aura Forms

### 1.1 O Problema

Hoje, um fluxo de formulário típico no Aura exige:

```python
# O dev precisa escrever isso tudo manualmente:

class CreatePostSchema(Schema):
    title: str
    body: str
    author_id: int
    tags: list[int]

@post("/posts")
async def create_post(body: Annotated[CreatePostSchema, Body()]) -> PostResponse:
    # Validação manual de FK
    async with db.session() as session:
        author = await UserRepository(session).get(body.author_id)
        if not author:
            raise ValidationException("author_id", "Usuário não encontrado")
        
        # Carregar tags uma por uma
        tags = []
        for tag_id in body.tags:
            tag = await TagRepository(session).get(tag_id)
            if not tag:
                raise ValidationException("tags", f"Tag {tag_id} não encontrada")
            tags.append(tag)
        
        # Criar post
        post = await PostRepository(session).create(
            title=body.title,
            body=body.body,
            author_id=body.author_id,
        )
        # Associar tags... mais boilerplate
```

Com Aura Forms, o mesmo fluxo seria:

```python
class PostForm(AuraForm):
    title    = CharField(max_length=200, required=True)
    body     = TextField(required=True)
    author   = ForeignKeyField(User, required=True)
    tags     = ManyToManyField(Tag, required=False)

@post("/posts")
async def create_post(form: Annotated[PostForm, FormData()]) -> PostResponse:
    post = await form.save()  # valida, carrega FKs, cria, associa M2M
    return PostResponse.model_validate(post, from_attributes=True)
```

---

### 1.2 Arquitetura dos Campos (Fields)

```
aura/forms/
├── __init__.py          # exports: AuraForm, CharField, IntField, ...
├── base.py              # AuraForm base class
├── fields.py            # todos os field types
├── validators.py        # validators reutilizáveis
├── widgets.py           # widgets HTML (renderização)
└── exceptions.py        # FormValidationError, FieldError
```

#### Hierarquia de Fields

```
Field (base)
├── CharField           → str, max_length, min_length, strip
├── TextField           → str longo (textarea widget padrão)
├── IntField            → int, min_value, max_value
├── FloatField          → float
├── DecimalField        → Decimal, max_digits, decimal_places
├── BoolField           → bool (checkbox widget)
├── EmailField          → CharField + validação RFC 5322
├── URLField            → CharField + validação URL
├── SlugField           → CharField + regex [a-z0-9-]
├── DateField           → datetime.date, input_formats
├── DateTimeField       → datetime.datetime, input_formats
├── TimeField           → datetime.time
├── UUIDField           → uuid.UUID
├── JSONField           → Any, schema validation opcional
├── FileField           → UploadFile (Starlette), max_size, allowed_types
├── ImageField          → FileField + validação de imagem
├── ChoiceField         → Literal[...] ou Enum
├── MultipleChoiceField → list de ChoiceField
├── ForeignKeyField     → carrega AuraModel por PK — CHAVE DO SISTEMA
└── ManyToManyField     → lista de AuraModel — CHAVE DO SISTEMA
```

#### Contrato de Field (Protocol)

```python
# aura/forms/fields.py

from typing import Any, Generic, TypeVar
from typing import Protocol

T = TypeVar("T")

class Field(Generic[T]):
    """Base para todos os campos de formulário."""

    label: str
    required: bool
    default: T | None
    validators: list[Callable[[T], Awaitable[None] | None]]
    widget: Widget
    error_messages: dict[str, str]

    async def to_python(self, raw: Any) -> T:
        """Converte raw input (string do form, JSON) para tipo Python."""
        raise NotImplementedError

    async def validate(self, value: T) -> None:
        """Valida o valor já convertido. Levanta FieldValidationError se inválido."""
        if self.required and value is None:
            raise FieldValidationError("Este campo é obrigatório.")
        for validator in self.validators:
            result = validator(value)
            if asyncio.iscoroutine(result):
                await result
```

#### ForeignKeyField — O mais importante

```python
class ForeignKeyField(Field[ModelT]):
    """Campo que valida existência de FK e carrega o objeto relacionado.

    Exemplo:
        author = ForeignKeyField(User, required=True)
        # Input: {"author": 42}
        # Output: form.cleaned_data["author"] == <User id=42>
    """

    def __init__(
        self,
        model: type[ModelT],
        *,
        required: bool = True,
        queryset: Callable[[AsyncSession], Awaitable[list[ModelT]]] | None = None,
        to_field: str = "id",
    ) -> None:
        self.model = model
        self.queryset = queryset
        self.to_field = to_field
        super().__init__(required=required)

    async def to_python(self, raw: Any, *, session: AsyncSession) -> ModelT | None:
        if raw is None or raw == "":
            return None
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            raise FieldValidationError(f"ID inválido: {raw!r}")

        if self.queryset:
            # queryset customizado — permite filtrar quais objetos são válidos
            valid_ids = {getattr(obj, self.to_field) for obj in await self.queryset(session)}
            if pk not in valid_ids:
                raise FieldValidationError(f"{self.model.__name__} não encontrado.")
            obj = await session.get(self.model, pk)
        else:
            obj = await session.get(self.model, pk)

        if obj is None:
            raise FieldValidationError(f"{self.model.__name__} com id {pk} não encontrado.")

        return obj
```

---

### 1.3 AuraForm — Classe Base

```python
class AuraForm:
    """Base para todos os formulários Aura.

    Uso básico:
        class PostForm(AuraForm):
            title  = CharField(max_length=200)
            author = ForeignKeyField(User)

        # Em um controller:
        @post("/posts")
        async def create(form: Annotated[PostForm, FormData()]) -> Response:
            if not await form.is_valid():
                return form.errors_response()  # 422 com detalhes
            post = await form.save()

    Ou com validação inline:
        @post("/posts")
        async def create(form: Annotated[PostForm, FormData()]) -> Response:
            post = await form.save()  # levanta FormValidationError (422) automaticamente
    """

    _fields: ClassVar[dict[str, Field[Any]]]
    _session: AsyncSession
    cleaned_data: dict[str, Any]
    errors: dict[str, list[str]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # Metaclass-like: coleta todos os Field como _fields
        cls._fields = {
            name: field
            for name, field in vars(cls).items()
            if isinstance(field, Field)
        }

    async def full_clean(self) -> bool:
        """Executa validação de todos os campos + clean() global."""
        self.errors = {}
        self.cleaned_data = {}

        for name, field in self._fields.items():
            raw = self._raw_data.get(name)
            try:
                if isinstance(field, (ForeignKeyField, ManyToManyField)):
                    value = await field.to_python(raw, session=self._session)
                else:
                    value = await field.to_python(raw)
                await field.validate(value)
                self.cleaned_data[name] = value
            except FieldValidationError as e:
                self.errors[name] = e.messages

        # Hook para validação cruzada de campos
        if not self.errors and hasattr(self, "clean"):
            try:
                await self.clean()
            except FormValidationError as e:
                self.errors["__all__"] = e.messages

        return not self.errors

    async def is_valid(self) -> bool:
        return await self.full_clean()

    async def save(self, *, commit: bool = True) -> Any:
        """Salva o form no banco. Levanta FormValidationError se inválido."""
        if not await self.full_clean():
            raise FormValidationError(self.errors)
        return await self._save(commit=commit)

    async def _save(self, *, commit: bool) -> Any:
        """Override em ModelForm para comportamento específico."""
        raise NotImplementedError("Use ModelForm para salvar no banco.")
```

---

### 1.4 ModelForm — Geração Automática a partir de AuraModel

O mais poderoso: gerar um form completo a partir de um model SQLAlchemy.

```python
class ModelForm(AuraForm):
    """Form gerado automaticamente a partir de um AuraModel.

    Exemplo:
        class PostForm(ModelForm):
            class Meta:
                model = Post
                fields = ["title", "body", "author", "tags"]
                # exclude = ["created_at", "updated_at"]  # alternativa
                widgets = {
                    "body": TextareaWidget(rows=10),
                }
    """

    class Meta:
        model: type[AuraModel]
        fields: list[str] | Literal["__all__"]
        exclude: list[str]
        widgets: dict[str, Widget]
        labels: dict[str, str]
        help_texts: dict[str, str]

    @classmethod
    def _build_fields_from_model(cls) -> dict[str, Field[Any]]:
        """Inspeciona colunas e relationships do model e gera Fields automaticamente."""
        meta = cls.Meta
        model = meta.model
        inspector = inspect(model)
        result: dict[str, Field[Any]] = {}

        for column in inspector.columns:
            if hasattr(meta, "fields") and column.name not in meta.fields:
                continue
            if hasattr(meta, "exclude") and column.name in meta.exclude:
                continue
            result[column.name] = _column_to_field(column)

        for rel in inspector.relationships:
            if hasattr(meta, "fields") and rel.key not in meta.fields:
                continue
            if rel.direction == MANYTOONE:
                result[rel.key] = ForeignKeyField(rel.mapper.class_)
            elif rel.direction == MANYTOMANY:
                result[rel.key] = ManyToManyField(rel.mapper.class_)

        return result

    async def _save(self, *, commit: bool) -> AuraModel:
        data = dict(self.cleaned_data)
        m2m_fields: dict[str, list[AuraModel]] = {}

        # Separar FK simples de M2M
        for name, value in list(data.items()):
            field = self._fields[name]
            if isinstance(field, ForeignKeyField) and isinstance(value, AuraModel):
                data[name + "_id"] = value.id
                del data[name]
            elif isinstance(field, ManyToManyField):
                m2m_fields[name] = value
                del data[name]

        if self._instance:
            # Update
            for key, value in data.items():
                setattr(self._instance, key, value)
            obj = self._instance
        else:
            # Create
            obj = self.Meta.model(**data)
            self._session.add(obj)

        if commit:
            await self._session.flush()
            await self._session.refresh(obj)

            # Associar M2M
            for field_name, related_objs in m2m_fields.items():
                collection = getattr(obj, field_name)
                collection.clear()
                collection.extend(related_objs)
            await self._session.flush()

        return obj
```

---

### 1.5 Renderização HTML (Widgets)

```python
# aura/forms/widgets.py

class Widget:
    """Renderiza um Field como HTML."""
    template: str

    def render(self, name: str, value: Any, attrs: dict[str, Any] | None = None) -> str:
        raise NotImplementedError


class TextInput(Widget):
    template = '<input type="text" name="{name}" value="{value}" {attrs}>'


class TextareaWidget(Widget):
    def __init__(self, rows: int = 4, cols: int = 40) -> None:
        self.rows = rows
        self.cols = cols

    template = '<textarea name="{name}" rows="{rows}" cols="{cols}">{value}</textarea>'


class SelectWidget(Widget):
    """Para ChoiceField e ForeignKeyField."""
    # Renderiza <select> com <option> para cada escolha possível

class CheckboxInput(Widget):
    template = '<input type="checkbox" name="{name}" {checked}>'

class FileInput(Widget):
    template = '<input type="file" name="{name}" accept="{accept}">'
```

#### Integração com Jinja2 Templates

```html
<!-- templates/post_form.html -->
{% for field in form %}
  <div class="field {% if field.errors %}has-error{% endif %}">
    {{ field.label_tag() }}
    {{ field.widget() }}
    {% for error in field.errors %}
      <span class="error">{{ error }}</span>
    {% endfor %}
  </div>
{% endfor %}
```

---

### 1.6 Integração com Routing (FormData binding)

```python
# aura/routing/params.py — novo param resolver

class FormData:
    """Marcador para injetar um AuraForm preenchido com dados do request."""

    async def resolve(
        self,
        request: AuraRequest,
        form_class: type[AuraForm],
        session: AsyncSession,
    ) -> AuraForm:
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            raw = await request.json()
        elif "multipart/form-data" in content_type:
            raw = dict(await request.form())
        elif "application/x-www-form-urlencoded" in content_type:
            raw = dict(await request.form())
        else:
            raw = {}

        form = form_class.__new__(form_class)
        form._raw_data = raw
        form._session = session
        form._instance = None
        return form
```

---

### 1.7 Async Validators customizados

```python
class PostForm(ModelForm):
    class Meta:
        model = Post
        fields = "__all__"

    title = CharField(max_length=200)
    slug  = SlugField()

    async def clean_slug(self) -> str:
        """Hook: clean_<fieldname> é chamado automaticamente após validação do campo."""
        slug = self.cleaned_data["slug"]
        exists = await PostRepository(self._session).exists(slug=slug)
        if exists:
            raise FieldValidationError("Este slug já está em uso.")
        return slug

    async def clean(self) -> None:
        """Validação cruzada de campos."""
        title = self.cleaned_data.get("title", "")
        slug = self.cleaned_data.get("slug", "")
        if title and slug and not slug.startswith(title[:5].lower()):
            raise FormValidationError("O slug deve começar com as primeiras letras do título.")
```

---

### 1.8 Dependências e extras

```toml
# pyproject.toml
[project.optional-dependencies]
forms = [
    "python-multipart>=0.0.9",  # já necessário para form data no Starlette
    "pillow>=10.0",              # apenas para ImageField
]
```

> `python-multipart` já é dependência de fato para qualquer POST com form. `pillow` é opcional e só ativa `ImageField`.

---

## Parte 2 — AuraQL: Query Builder Fluente

### 2.1 O Problema

O `Repository[T]` atual cobre CRUD simples. Para qualquer query mais rica, o dev hoje precisa descer para SQLAlchemy puro:

```python
# O dev escreve isso — verboso e sem type safety no result
stmt = (
    select(Post)
    .where(and_(Post.active == True, Post.author_id == user_id))
    .options(selectinload(Post.tags), joinedload(Post.author))
    .order_by(Post.created_at.desc())
    .limit(20)
    .offset(0)
)
result = await session.execute(stmt)
posts = list(result.scalars().all())
```

Com AuraQL, o mesmo seria:

```python
posts = await (
    Post.objects
    .filter(active=True, author_id=user_id)
    .include("tags", "author")
    .order_by("-created_at")
    .limit(20)
    .all()
)
```

---

### 2.2 Filosofia do Design

Inspirações e diferenças:

| Framework | O que inspira | O que evitar |
|---|---|---|
| **Django ORM** | `.filter()`, `.exclude()`, `.order_by("-field")`, `.select_related()` | Ser síncrono; lazy loading opaco |
| **Peewee** | API fluente simples, `.where(Model.field == value)` | Falta de type safety |
| **Prisma (TypeScript)** | `.include()` declarativo, result types gerados | Geração de código em build time |
| **SQLAlchemy 2.x** | Base — todo o AuraQL compila para select() nativo | Verbosidade da API |

**Princípio central:** AuraQL é uma **camada de açúcar** sobre SQLAlchemy — não um ORM novo. Toda query AuraQL compila para `select()` nativo e pode ser inspecionada.

---

### 2.3 Arquitetura

```
aura/orm/
├── base.py          # AuraModel (atual) + mixin QueryMixin
├── query.py         # QuerySet[T] — o core do AuraQL ← NOVO
├── expressions.py   # Q() para queries complexas ← NOVO
├── aggregates.py    # Count, Sum, Avg, Min, Max ← NOVO
├── repository.py    # Repository[T] (atual) — mantido
└── session.py       # DatabaseManager (atual)
```

---

### 2.4 QuerySet[T] — API Completa

```python
# aura/orm/query.py

from __future__ import annotations
from typing import Any, Generic, TypeVar, TYPE_CHECKING
from sqlalchemy import select, and_, or_, func, desc, asc
from sqlalchemy.orm import selectinload, joinedload, contains_eager

ModelT = TypeVar("ModelT", bound="AuraModel")


class QuerySet(Generic[ModelT]):
    """
    Query builder fluente e async para AuraModel.

    Cada método retorna um novo QuerySet (imutável).
    A query só é executada ao chamar .all(), .first(), .get(), .count(), etc.
    """

    def __init__(
        self,
        model: type[ModelT],
        session: AsyncSession | None = None,
    ) -> None:
        self._model = model
        self._session = session
        self._filters: list[Any] = []
        self._excludes: list[Any] = []
        self._order_by_clauses: list[Any] = []
        self._limit_val: int | None = None
        self._offset_val: int = 0
        self._select_related: list[str] = []     # joinedload (one-to-one, many-to-one)
        self._prefetch_related: list[str] = []   # selectinload (one-to-many, many-to-many)
        self._annotations: dict[str, Any] = {}
        self._distinct: bool = False
        self._for_update: bool = False

    # ──────────────────────────────────────────
    # Filtering
    # ──────────────────────────────────────────

    def filter(self, *q_objects: Q, **kwargs: Any) -> QuerySet[ModelT]:
        """Adiciona condições AND.

        Suporta lookups Django-style:
            .filter(name__icontains="john")
            .filter(created_at__gte=date(2024, 1, 1))
            .filter(Q(active=True) | Q(role="admin"))
        """
        qs = self._clone()
        for q in q_objects:
            qs._filters.append(q._to_sqla(self._model))
        for key, value in kwargs.items():
            qs._filters.append(_resolve_lookup(self._model, key, value))
        return qs

    def exclude(self, *q_objects: Q, **kwargs: Any) -> QuerySet[ModelT]:
        """Adiciona condições NOT AND (equivalente a .filter(~Q(...)))."""
        qs = self._clone()
        conditions = [q._to_sqla(self._model) for q in q_objects]
        conditions += [_resolve_lookup(self._model, k, v) for k, v in kwargs.items()]
        qs._excludes.append(~and_(*conditions))
        return qs

    # ──────────────────────────────────────────
    # Ordering
    # ──────────────────────────────────────────

    def order_by(self, *fields: str) -> QuerySet[ModelT]:
        """Ordena por campos. Prefixo '-' = descendente.

        .order_by("-created_at", "name")
        """
        qs = self._clone()
        for field in fields:
            if field.startswith("-"):
                col = getattr(self._model, field[1:])
                qs._order_by_clauses.append(desc(col))
            else:
                col = getattr(self._model, field)
                qs._order_by_clauses.append(asc(col))
        return qs

    # ──────────────────────────────────────────
    # Slicing / Pagination
    # ──────────────────────────────────────────

    def limit(self, n: int) -> QuerySet[ModelT]:
        qs = self._clone()
        qs._limit_val = n
        return qs

    def offset(self, n: int) -> QuerySet[ModelT]:
        qs = self._clone()
        qs._offset_val = n
        return qs

    def page(self, number: int, size: int = 20) -> QuerySet[ModelT]:
        """Atalho para .limit(size).offset((number-1)*size)."""
        return self.limit(size).offset((number - 1) * size)

    # ──────────────────────────────────────────
    # Eager Loading de Relacionamentos
    # ──────────────────────────────────────────

    def include(self, *relationships: str) -> QuerySet[ModelT]:
        """Eager loading de relacionamentos (evita N+1).

        Detecta automaticamente o tipo de relationship:
        - many-to-one / one-to-one → joinedload (1 query com JOIN)
        - one-to-many / many-to-many → selectinload (1 query extra por rel)

        Suporta nested:
            .include("author")               # carrega Post.author
            .include("author.profile")       # carrega User.profile também
            .include("tags", "comments")     # múltiplos

        Exemplo:
            posts = await Post.objects.include("author", "tags").filter(active=True).all()
            # posts[0].author → User já carregado (sem query extra)
            # posts[0].tags   → list[Tag] já carregado (sem query extra)
        """
        qs = self._clone()
        for rel in relationships:
            # Detectar se é select_related (to-one) ou prefetch_related (to-many)
            # A detecção real acontece em _build_stmt via inspeção do mapper
            qs._prefetch_related.append(rel)  # default: selectinload é mais seguro
        return qs

    def select_related(self, *relationships: str) -> QuerySet[ModelT]:
        """Força joinedload (JOIN) para relationships to-one. Mais eficiente quando
        você sabe que vai acessar o relacionamento para todos os resultados."""
        qs = self._clone()
        qs._select_related.extend(relationships)
        return qs

    # ──────────────────────────────────────────
    # Anotações / Agregações inline
    # ──────────────────────────────────────────

    def annotate(self, **kwargs: Any) -> QuerySet[ModelT]:
        """Adiciona campos computados ao resultado.

        .annotate(post_count=Count("posts"))
        .annotate(total_price=Sum("items__price"))
        """
        qs = self._clone()
        qs._annotations.update(kwargs)
        return qs

    def distinct(self) -> QuerySet[ModelT]:
        qs = self._clone()
        qs._distinct = True
        return qs

    def for_update(self) -> QuerySet[ModelT]:
        """SELECT FOR UPDATE — lock otimista para operações críticas."""
        qs = self._clone()
        qs._for_update = True
        return qs

    # ──────────────────────────────────────────
    # Terminal — executam a query
    # ──────────────────────────────────────────

    async def all(self) -> list[ModelT]:
        """Executa a query e retorna todos os resultados."""
        stmt = self._build_stmt()
        result = await self._get_session().execute(stmt)
        return list(result.scalars().unique().all())

    async def first(self) -> ModelT | None:
        """Retorna o primeiro resultado ou None."""
        stmt = self._build_stmt().limit(1)
        result = await self._get_session().execute(stmt)
        return result.scalars().first()

    async def get(self, **kwargs: Any) -> ModelT:
        """Retorna exatamente um resultado. Levanta exceção se 0 ou >1."""
        qs = self.filter(**kwargs)
        stmt = qs._build_stmt()
        result = await self._get_session().execute(stmt)
        rows = list(result.scalars().unique().all())
        if not rows:
            raise NotFoundException(f"{self._model.__name__} não encontrado.")
        if len(rows) > 1:
            raise MultipleObjectsReturned(
                f"get() retornou {len(rows)} objetos para {self._model.__name__}."
            )
        return rows[0]

    async def get_or_none(self, **kwargs: Any) -> ModelT | None:
        """Como .get() mas retorna None em vez de levantar NotFoundException."""
        try:
            return await self.get(**kwargs)
        except NotFoundException:
            return None

    async def count(self) -> int:
        """COUNT(*) com os filtros aplicados."""
        stmt = (
            select(func.count())
            .select_from(self._model)
        )
        for condition in self._filters + self._excludes:
            stmt = stmt.where(condition)
        result = await self._get_session().execute(stmt)
        return result.scalar() or 0

    async def exists(self) -> bool:
        """Retorna True se existe pelo menos um resultado."""
        return await self.count() > 0

    async def paginate(
        self,
        page: int = 1,
        per_page: int = 20,
    ) -> Page[ModelT]:
        """Paginação com metadados. Executa 2 queries (COUNT + SELECT)."""
        total = await self.count()
        items = await self.page(page, per_page).all()
        return Page(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            has_next=page * per_page < total,
        )

    async def aggregate(self, **kwargs: Any) -> dict[str, Any]:
        """Agrega valores. Ex: .aggregate(total=Sum("price"), avg=Avg("price"))"""
        # implementação: compila funções de agregação e executa em 1 query
        ...

    async def values(self, *fields: str) -> list[dict[str, Any]]:
        """Retorna dicts em vez de objetos. Útil para serialização sem overhead."""
        ...

    async def values_list(self, *fields: str, flat: bool = False) -> list[Any]:
        """Retorna tuples ou valores flat."""
        ...

    async def bulk_create(self, items: list[dict[str, Any]]) -> list[ModelT]:
        ...

    async def bulk_update(self, ids: list[int], **data: Any) -> int:
        """UPDATE ... WHERE id IN (...) — uma query, não N."""
        from sqlalchemy import update
        stmt = (
            update(self._model)
            .where(self._model.id.in_(ids))
            .values(**data)
            .execution_options(synchronize_session="fetch")
        )
        result = await self._get_session().execute(stmt)
        return result.rowcount

    async def bulk_delete(self) -> int:
        """DELETE com os filtros aplicados — uma query."""
        from sqlalchemy import delete
        stmt = delete(self._model)
        for condition in self._filters:
            stmt = stmt.where(condition)
        result = await self._get_session().execute(stmt)
        return result.rowcount

    # ──────────────────────────────────────────
    # Internals
    # ──────────────────────────────────────────

    def _build_stmt(self) -> Select[Any]:
        stmt = select(self._model)

        # Filters
        all_conditions = self._filters + self._excludes
        if all_conditions:
            stmt = stmt.where(and_(*all_conditions))

        # Eager loading — prefetch (selectinload)
        for rel_path in self._prefetch_related:
            loader = _build_loader(self._model, rel_path, strategy="selectin")
            stmt = stmt.options(loader)

        # Eager loading — select_related (joinedload)
        for rel_path in self._select_related:
            loader = _build_loader(self._model, rel_path, strategy="joined")
            stmt = stmt.options(loader)

        # Ordering
        if self._order_by_clauses:
            stmt = stmt.order_by(*self._order_by_clauses)

        # Pagination
        if self._limit_val is not None:
            stmt = stmt.limit(self._limit_val)
        if self._offset_val:
            stmt = stmt.offset(self._offset_val)

        # Distinct
        if self._distinct:
            stmt = stmt.distinct()

        # FOR UPDATE
        if self._for_update:
            stmt = stmt.with_for_update()

        return stmt

    def _clone(self) -> QuerySet[ModelT]:
        """Cria cópia rasa para imutabilidade da chain."""
        import copy
        qs = QuerySet(self._model, self._session)
        qs._filters = list(self._filters)
        qs._excludes = list(self._excludes)
        qs._order_by_clauses = list(self._order_by_clauses)
        qs._limit_val = self._limit_val
        qs._offset_val = self._offset_val
        qs._select_related = list(self._select_related)
        qs._prefetch_related = list(self._prefetch_related)
        qs._annotations = dict(self._annotations)
        qs._distinct = self._distinct
        qs._for_update = self._for_update
        return qs

    def _get_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError(
                "QuerySet requer uma sessão. Use 'async with db.session() as s: "
                "await Post.objects.using(s).filter(...).all()'"
            )
        return self._session

    def using(self, session: AsyncSession) -> QuerySet[ModelT]:
        """Associa uma sessão ao QuerySet."""
        qs = self._clone()
        qs._session = session
        return qs

    def sql(self) -> str:
        """Inspeciona a query SQL gerada sem executar. Útil para debug."""
        from sqlalchemy.dialects import postgresql
        stmt = self._build_stmt()
        return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
```

---

### 2.5 Q() — Queries Complexas

```python
class Q:
    """Encapsula condições para combinação com & e |.

    Equivalente ao Q() do Django ORM.

    Exemplos:
        # OR simples
        Q(active=True) | Q(role="admin")

        # AND explícito
        Q(active=True) & Q(email__endswith="@empresa.com")

        # NOT
        ~Q(deleted=True)

        # Composição complexa
        (Q(role="admin") | Q(role="moderator")) & ~Q(banned=True)
    """

    def __init__(self, **kwargs: Any) -> None:
        self._conditions = kwargs
        self._connector = "AND"
        self._negated = False
        self._children: list[Q] = []

    def __and__(self, other: Q) -> Q:
        q = Q()
        q._connector = "AND"
        q._children = [self, other]
        return q

    def __or__(self, other: Q) -> Q:
        q = Q()
        q._connector = "OR"
        q._children = [self, other]
        return q

    def __invert__(self) -> Q:
        q = Q(**self._conditions)
        q._connector = self._connector
        q._children = list(self._children)
        q._negated = not self._negated
        return q

    def _to_sqla(self, model: type[AuraModel]) -> Any:
        """Compila para expressão SQLAlchemy."""
        if self._children:
            compiled = [child._to_sqla(model) for child in self._children]
            expr = and_(*compiled) if self._connector == "AND" else or_(*compiled)
        else:
            parts = [_resolve_lookup(model, k, v) for k, v in self._conditions.items()]
            expr = and_(*parts)

        return ~expr if self._negated else expr
```

---

### 2.6 Lookups Django-style

```python
# aura/orm/lookups.py

LOOKUPS: dict[str, Callable[[Any, Any], Any]] = {
    "exact":       lambda col, v: col == v,
    "iexact":      lambda col, v: func.lower(col) == func.lower(v),
    "contains":    lambda col, v: col.contains(v),
    "icontains":   lambda col, v: col.ilike(f"%{v}%"),
    "startswith":  lambda col, v: col.startswith(v),
    "istartswith": lambda col, v: col.ilike(f"{v}%"),
    "endswith":    lambda col, v: col.endswith(v),
    "iendswith":   lambda col, v: col.ilike(f"%{v}"),
    "gt":          lambda col, v: col > v,
    "gte":         lambda col, v: col >= v,
    "lt":          lambda col, v: col < v,
    "lte":         lambda col, v: col <= v,
    "in":          lambda col, v: col.in_(v),
    "not_in":      lambda col, v: col.not_in(v),
    "is_null":     lambda col, v: col.is_(None) if v else col.is_not(None),
    "range":       lambda col, v: col.between(v[0], v[1]),
    "date":        lambda col, v: func.date(col) == v,
    "year":        lambda col, v: func.extract("year", col) == v,
    "month":       lambda col, v: func.extract("month", col) == v,
    "day":         lambda col, v: func.extract("day", col) == v,
    "regex":       lambda col, v: col.regexp_match(v),
    "iregex":      lambda col, v: col.regexp_match(v, flags="i"),
}

def _resolve_lookup(model: type[AuraModel], key: str, value: Any) -> Any:
    """
    Resolve 'field__lookup' para expressão SQLAlchemy.

    Exemplos:
        "name__icontains" → User.name.ilike("%joao%")
        "age__gte"        → User.age >= 18
        "author__id"      → resolve FK traversal (author_id == value)
        "created_at__year"→ extract(year, created_at) == 2024
    """
    parts = key.split("__")

    # Lookup simples: "name" ou "name__exact"
    if len(parts) == 1 or (len(parts) == 2 and parts[1] in LOOKUPS):
        field_name = parts[0]
        lookup = parts[1] if len(parts) == 2 else "exact"
        col = getattr(model, field_name)
        return LOOKUPS[lookup](col, value)

    # FK traversal: "author__name" → JOIN necessário (flag para QuerySet)
    # Implementação fase 2 — por ora, levantar NotImplementedError com mensagem clara
    raise NotImplementedError(
        f"FK traversal ('{key}') ainda não suportado. "
        "Use .join() ou SQLAlchemy direto para queries com JOIN."
    )
```

---

### 2.7 Aggregates

```python
# aura/orm/aggregates.py

class Aggregate:
    def __init__(self, field: str, distinct: bool = False) -> None:
        self.field = field
        self.distinct = distinct

    def _to_sqla(self, model: type[AuraModel]) -> Any:
        raise NotImplementedError


class Count(Aggregate):
    def _to_sqla(self, model: type[AuraModel]) -> Any:
        col = getattr(model, self.field) if self.field != "*" else func.count()
        return func.count(col.distinct() if self.distinct else col)


class Sum(Aggregate):
    def _to_sqla(self, model: type[AuraModel]) -> Any:
        return func.sum(getattr(model, self.field))


class Avg(Aggregate):
    def _to_sqla(self, model: type[AuraModel]) -> Any:
        return func.avg(getattr(model, self.field))


class Min(Aggregate):
    def _to_sqla(self, model: type[AuraModel]) -> Any:
        return func.min(getattr(model, self.field))


class Max(Aggregate):
    def _to_sqla(self, model: type[AuraModel]) -> Any:
        return func.max(getattr(model, self.field))
```

Uso:

```python
stats = await Post.objects.using(session).filter(active=True).aggregate(
    total=Count("id"),
    avg_views=Avg("view_count"),
    max_views=Max("view_count"),
)
# {"total": 1500, "avg_views": 42.3, "max_views": 9841}
```

---

### 2.8 Integração com AuraModel — `objects` manager

```python
# aura/orm/base.py — adicionar ao AuraModel

class QueryMixin:
    """Mixin que adiciona .objects ao AuraModel."""

    @classmethod
    @property
    def objects(cls) -> QuerySet[Self]:
        """Ponto de entrada para queries.

        Uso:
            # Dentro de async with db.session() as session:
            users = await User.objects.using(session).filter(active=True).all()

            # Com session injetada (quando DI Scoped estiver pronto):
            users = await User.objects.filter(active=True).all()
        """
        return QuerySet(cls)


class AuraModel(_AuraRegistry, QueryMixin):
    __abstract__ = True
    # ... resto igual
```

---

### 2.9 N+1 Detection em Debug Mode

Um dos problemas mais silenciosos em ORMs: o dev chama `.all()` e depois acessa `post.author` em um loop, gerando N queries extras.

```python
class QuerySet(Generic[ModelT]):
    _n_plus_one_check: ClassVar[bool] = False  # ativo via AURA__DEBUG=true

    async def all(self) -> list[ModelT]:
        if self._n_plus_one_check and not self._prefetch_related and not self._select_related:
            # Inspeciona se o model tem relationships definidas
            rels = _get_model_relationships(self._model)
            if rels:
                import warnings
                warnings.warn(
                    f"QuerySet<{self._model.__name__}> tem relacionamentos "
                    f"({', '.join(rels)}) mas nenhum .include() foi chamado. "
                    f"Isso pode causar N+1 queries. Use .include('{rels[0]}') para "
                    f"carregar relacionamentos com eficiência.",
                    AuraN1Warning,
                    stacklevel=3,
                )
        # ... executa normalmente
```

---

### 2.10 Query Profiling — `X-Query-Count`

```python
# aura/orm/profiling.py

class QueryProfiler:
    """Conta e loga queries SQL por request quando AURA__DEBUG=true."""

    def __init__(self) -> None:
        self._count = 0
        self._queries: list[str] = []

    def record(self, sql: str, duration_ms: float) -> None:
        self._count += 1
        self._queries.append(f"[{duration_ms:.1f}ms] {sql[:200]}")

    def summary(self) -> str:
        return f"{self._count} queries"
```

Middleware adiciona `X-Query-Count: 3` na resposta em modo debug.

---

## Parte 3 — Plano de Implementação

### 3.1 Fases de Entrega

```
v0.5.0 — AuraQL Core
├── QuerySet[T] com filter/exclude/order_by/limit/offset/all/first/get/count/exists/paginate
├── Q() com __and__, __or__, __invert__
├── Lookups: exact, icontains, gte, lte, in, is_null (os 90% dos casos)
├── .include() com selectinload automático (sem nested ainda)
├── .sql() para debug
├── Integração: AuraModel.objects → QuerySet
├── bulk_update/bulk_delete via UPDATE/DELETE em vez de N queries (melhora o atual)
└── 60+ testes (unit + integration com SQLite async)

v0.5.1 — AuraQL Advanced
├── Aggregates: Count, Sum, Avg, Min, Max
├── .aggregate() e .annotate()
├── .values() e .values_list()
├── Lookups: startswith, endswith, range, year, month, day, regex
├── select_related() com joinedload
├── .include() nested: .include("author.profile")
├── N+1 detection em AURA__DEBUG=true
└── X-Query-Count middleware

v0.6.0 — Aura Forms
├── Fields: CharField, IntField, FloatField, BoolField, EmailField, DateField, ChoiceField
├── ForeignKeyField com carregamento async
├── ManyToManyField com carregamento async
├── AuraForm.full_clean(), .is_valid(), clean_<field>() hooks, .clean() global
├── FormData() binding no routing (JSON + form-data + multipart)
├── FormValidationError → resposta 422 automática com campo + mensagem
└── 40+ testes

v0.6.1 — ModelForm + Widgets
├── ModelForm com geração automática a partir de AuraModel
├── Widgets: TextInput, TextareaWidget, SelectWidget, CheckboxInput, FileInput
├── Renderização HTML via Jinja2 integration
├── ImageField com validação Pillow
└── Documentação completa com exemplos
```

---

### 3.2 Decisões Arquiteturais a Resolver Antes

Estas questões precisam de revisão formal do **Arquiteto** antes de qualquer implementação:

#### Decisão 1 — Session em QuerySet: injeção explícita vs context var

**Opção A — Explícita (recomendada para v0.5.0):**
```python
async with db.session() as s:
    posts = await Post.objects.using(s).filter(active=True).all()
```
Prós: explícito, testável, sem magia  
Contras: verboso

**Opção B — Context Var (possível após Scoped DI):**
```python
# Session resolvida via contextvars — injetada pelo middleware
posts = await Post.objects.filter(active=True).all()
```
Prós: ergonomia máxima (Django-like)  
Contras: magia implícita, dificulta testes

**Recomendação:** Implementar A em v0.5.0. Adicionar B como opcional quando o Scoped DI Container estiver pronto (já no roadmap).

#### Decisão 2 — FK Traversal em lookups

`User.objects.filter(posts__title__icontains="aura")` requer JOIN automático.

Django resolve isso com inspeção de metadata. É poderoso mas complexo de implementar corretamente.

**Recomendação v0.5.0:** `NotImplementedError` com mensagem clara ("Use .join() ou SQLAlchemy direto"). Implementar em v0.5.2 ou v0.6.x.

#### Decisão 3 — Coexistência Repository[T] e QuerySet

Dois estilos para o mesmo propósito pode confundir.

**Recomendação:** Manter `Repository[T]` como está (não é breaking change). `QuerySet` é uma camada adicional mais poderosa. Documentar: "Repository para CRUD simples em Services. QuerySet para queries complexas."

#### Decisão 4 — AuraForm vs Pydantic Schema

Não substituir `Schema` (Pydantic) por `AuraForm`. São ferramentas diferentes:
- `Schema`: validação de dados puros (JSON API, DTOs, response models)
- `AuraForm`: formulários com estado, renderização HTML, FKs, arquivos, M2M

---

### 3.3 Critérios de Aceite Mínimos (DoD)

**AuraQL v0.5.0 está pronto quando:**

```
✅ Post.objects.using(session).filter(active=True).all() → list[Post]
✅ Post.objects.using(session).filter(Q(active=True) | Q(featured=True)).all() → list[Post]
✅ Post.objects.using(session).filter(title__icontains="aura").order_by("-created_at").limit(10).all()
✅ Post.objects.using(session).include("author", "tags").all() → posts com author e tags carregados (sem N+1)
✅ Post.objects.using(session).filter(active=True).paginate(page=2, per_page=20) → Page[Post]
✅ Post.objects.using(session).filter(active=True).count() → int
✅ Post.objects.using(session).get(id=42) → Post ou NotFoundException
✅ Post.objects.using(session).sql() → string SQL legível para debug
✅ pytest tests/test_querybuilder.py → 60+ testes passando
✅ mypy aura/orm/ → 0 erros
✅ ruff check aura/orm/ → 0 erros
```

**Aura Forms v0.6.0 está pronto quando:**

```
✅ class PostForm(AuraForm) com CharField + ForeignKeyField funciona
✅ await form.save() cria objeto no banco e retorna instância
✅ await form.is_valid() retorna False com form.errors populados quando inválido
✅ FormData() no routing aceita JSON e multipart/form-data
✅ clean_<field>() async hook é chamado
✅ ForeignKeyField levanta erro 422 quando FK não existe no banco
✅ pytest tests/test_forms.py → 40+ testes passando
✅ mypy aura/forms/ → 0 erros
```

---

## Parte 4 — Benchmarks e Comparações

### 4.1 AuraQL vs Alternativas

| Operação | SQLAlchemy direto | Repository[T] atual | AuraQL (meta) |
|---|---|---|---|
| Listar com filtro | 8 linhas | 1 linha | 1 linha |
| Listar com eager load | 12 linhas | não suporta | 1 linha |
| Paginação com total | 15 linhas | 1 linha | 1 linha |
| Aggregate | 10 linhas | não suporta | 1 linha |
| Query complexa OR | 8 linhas | não suporta | 1 linha com Q() |
| Raw SQL | ✅ sempre disponível | ✅ via `self.session` | ✅ via `.using(session)` direto |

### 4.2 AuraQL vs Django ORM

| Feature | Django ORM | AuraQL |
|---|---|---|
| Async nativo | ❌ (thread-pool) | ✅ |
| Type-safe | ❌ (sem generics) | ✅ (QuerySet[T]) |
| `.filter()` / `.exclude()` | ✅ | ✅ |
| Lookups `field__icontains` | ✅ | ✅ |
| Q() para OR/AND | ✅ | ✅ |
| `.select_related()` | ✅ | ✅ |
| `.prefetch_related()` | ✅ | ✅ (.include()) |
| FK traversal em filter | ✅ | ❌ v0.5 / futuro |
| `.annotate()` | ✅ | ✅ v0.5.1 |
| `.aggregate()` | ✅ | ✅ v0.5.1 |
| `.values()` | ✅ | ✅ v0.5.1 |
| Migrations integradas | ✅ | ✅ (Alembic) |
| N+1 detection | ❌ (só django-debug-toolbar) | ✅ em debug mode |

### 4.3 AuraForm vs Django Forms

| Feature | Django Forms | AuraForm |
|---|---|---|
| Fields com validação | ✅ | ✅ |
| Async validators | ❌ | ✅ |
| ForeignKeyField async | ❌ | ✅ |
| ModelForm automático | ✅ | ✅ |
| HTML widgets | ✅ | ✅ |
| Jinja2 integration | opcional | ✅ nativo |
| JSON input (API) | ❌ | ✅ |
| multipart/form-data | ✅ | ✅ |
| Type-safe | ❌ | ✅ |

---

## Parte 5 — Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| QuerySet imutável quebra em edge cases de clone | Médio | Alto | 100% de cobertura de testes nos métodos de clone |
| N+1 warning falso positivo em código correto | Baixo | Médio | Warning só com `AURA__DEBUG=true`, fácil de silenciar |
| ModelForm com model complexo (herança, mixins) | Médio | Médio | Implementar progressivamente, começar com models simples |
| ForeignKeyField com queryset grande carrega tudo | Médio | Alto | `queryset=` recebe callable — o dev controla o subset |
| AuraQL shadow de `Repository[T]` divide comunidade | Médio | Baixo | Documentar claramente quando usar cada um |
| mypy com Generic[T] em QuerySet é complexo | Alto | Médio | Testar mypy strict desde o primeiro commit do módulo |

---

## Referências

- Django Forms: https://docs.djangoproject.com/en/5.0/ref/forms/
- Django ORM QuerySet: https://docs.djangoproject.com/en/5.0/ref/models/querysets/
- SQLAlchemy 2.x Relationships: https://docs.sqlalchemy.org/en/20/orm/relationships.html
- SQLAlchemy Eager Loading: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
- Prisma Client Python: https://prisma-client-py.readthedocs.io/
- Litestar Repository Pattern: https://docs.litestar.dev/latest/usage/dto/
- WTForms: https://wtforms.readthedocs.io/
- NestJS Pipes (validação): https://docs.nestjs.com/pipes

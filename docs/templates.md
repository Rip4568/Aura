# Templates — HTML + CSS + JS com Aura

## Por que o sistema de templates do Django/Flask é problemático

### O problema central: contexto sem spec

Em Django e Flask, o contexto de template é um `dict` livre:

```python
# Django — sem tipo, sem validação, sem contrato
def user_list(request):
    return render(request, "users.html", {
        "users": User.objects.all(),  # tipe? validado? N+1?
        "total": User.objects.count(), # query separada!
        "tile": "Users",  # typo: deveria ser "title" — ninguém vê até renderizar
    })
```

Consequências:
- ❌ Typo no nome da variável → template silencioso, sem erro
- ❌ Tipo errado → erro apenas em produção quando o template acessa o atributo
- ❌ Zero IDE support — `{{ user.??? }}` no template é invisível para o editor
- ❌ Impossível testar o contexto sem renderizar HTML

### O problema do N+1 em templates

```django
{# Django template — armadilha clássica #}
{% for post in posts %}
  <h2>{{ post.title }}</h2>
  <p>Por: {{ post.author.name }}</p>   {# → query por post! #}
  <span>{{ post.comments.count }}</span>  {# → mais uma query! #}
{% endfor %}
```

Com 50 posts: **1 + 50 + 50 = 101 queries** para renderizar uma página.

### Django-Ninja tentou resolver — mas apenas para JSON

Django-Ninja substituiu os serializers do DRF por Pydantic e adicionou async. Mas **ignorou completamente a renderização HTML**. O problema de contexto sem spec, N+1 em templates e ausência de componentes ficou sem solução.

---

## A solução Aura: TemplateContext + Componentes + htmx

### Instalação

```bash
pip install "aura-web[templates]"
# ou
pip install "aura-web[all]"
```

### Configuração

```python
from aura import Aura
from aura.templates import AuraTemplateModule

app = Aura(
    modules=[
        AuraTemplateModule.for_root(
            "templates",          # pasta de templates (pode ser múltiplas)
            auto_reload=True,     # hot reload em dev (sem restart!)
            static_url_prefix="/static",
        ),
        UserModule,
        PostModule,
    ],
    title="My App",
)
```

---

## TemplateContext — o contrato do template

`TemplateContext` é um modelo Pydantic. Ao invés de um `dict` livre, você **declara o que o template precisa** como uma classe:

```python
from aura.templates import TemplateContext
from datetime import datetime

class UserListContext(TemplateContext):
    title: str
    users: list[UserResponse]
    total: int
    page: int = 1
    page_size: int = 20
    
    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size
    
    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages
```

Benefícios imediatos:
- ✅ **Validado antes de renderizar** — campo faltando → erro Python claro, não erro no template
- ✅ **IDE autocomplete** — o editor sabe exatamente o que o template pode usar
- ✅ **Testável em isolamento** — testar `context.total_pages` sem renderizar HTML
- ✅ **Documentação automática** — a spec do template está no código

---

## render() — renderizando templates

```python
from aura import get
from aura.templates import render, HtmlResponse, TemplateContext

class UserListContext(TemplateContext):
    title: str
    users: list[UserResponse]
    total: int

class UserController:
    def __init__(self, service: UserService) -> None:
        self.service = service

    @get("/users")
    async def list_users(self) -> HtmlResponse:
        users = await self.service.list()
        return await render("users/list.html", UserListContext(
            title="All Users",
            users=users,
            total=len(users),
        ))
```

**Template** (`templates/users/list.html`):
```html
{% extends "base.html" %}

{% block content %}
<h1>{{ title }}</h1>
<p>{{ total }} users total</p>

<ul>
  {% for user in users %}
    <li>{{ user.name }} — {{ user.email }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

### @html decorator

Para rotas que sempre retornam HTML, use `@html` ao invés de `@get`:

```python
from aura.templates import html

class HomeController:
    @html("/")
    async def home(self) -> HtmlResponse:
        return await render("home.html", HomeContext(title="Home"))
    
    @html("/about")
    async def about(self) -> HtmlResponse:
        return await render("about.html", {"title": "About"})
```

---

## N+1: contexto construído em Python, nunca em templates

O Aura força boas práticas: toda a lógica de dados fica no Python, o template apenas exibe:

```python
# ✅ CORRETO — queries eager-loaded em Python
class PostListContext(TemplateContext):
    posts: list[PostItemContext]  # dados já prontos

class PostItemContext(TemplateContext):
    title: str
    author_name: str    # ← string pura, não objeto ORM
    comment_count: int  # ← int puro, não queryset

class PostController:
    @html("/posts")
    async def list_posts(self) -> HtmlResponse:
        # Uma query com join — não N+1
        from sqlalchemy.orm import selectinload
        posts = await db.session.execute(
            select(Post).options(
                selectinload(Post.author),
                selectinload(Post.comments),
            )
        )
        
        return await render("posts/list.html", PostListContext(
            posts=[
                PostItemContext(
                    title=p.title,
                    author_name=p.author.name,        # já carregado
                    comment_count=len(p.comments),    # já carregado
                )
                for p in posts.scalars()
            ]
        ))
```

```html
{# ✅ Template apenas exibe — sem queries #}
{% for post in posts %}
  <article>
    <h2>{{ post.title }}</h2>
    <p>By {{ post.author_name }}</p>
    <span>{{ post.comment_count }} comments</span>
  </article>
{% endfor %}
```

---

## Componentes — reutilização com props tipadas

O problema dos `{% include %}` do Django: passam o contexto inteiro, sem contrato. No Aura, componentes têm Props validadas:

```python
# components/user_card.py
from aura.templates import Component, TemplateContext

class UserCardProps(TemplateContext):
    user: UserResponse
    show_email: bool = False
    highlight: bool = False

class UserCard(Component):
    template = "components/user_card.html"
    Props = UserCardProps
    name = "user_card"  # nome usado no template
```

**Template do componente** (`templates/components/user_card.html`):
```html
<div class="card {% if highlight %}card--highlight{% endif %}">
  <h3>{{ user.name }}</h3>
  {% if show_email %}
    <p>{{ user.email }}</p>
  {% endif %}
</div>
```

**Usando em templates**:
```html
{# Renderiza o componente com props validadas #}
{{ component("user_card", user=user, show_email=True) }}

{# Em um loop #}
{% for user in users %}
  {{ component("user_card", user=user, highlight=loop.first) }}
{% endfor %}
```

**Usando em Python** (para testes ou email):
```python
from components.user_card import UserCard, UserCardProps

html = await UserCard(engine).render(UserCardProps(
    user=user,
    show_email=True,
))
```

---

## htmx — HTML-over-the-wire

htmx permite atualizar partes da página com requisições ao servidor que retornam **fragmentos HTML** — sem JSON, sem SPA, sem build step.

### Detectando requests htmx

```python
from aura import get
from aura.core.request import AuraRequest
from aura.templates import render, HtmlResponse, TemplateContext

class UserListContext(TemplateContext):
    users: list[UserResponse]
    total: int

class UserController:
    @get("/users")
    async def list_users(self, request: AuraRequest) -> HtmlResponse:
        users = await self.service.list()
        ctx = UserListContext(users=users, total=len(users))
        
        # htmx pede apenas o fragmento, não a página inteira
        if request.htmx.is_htmx:
            return await render("partials/user_rows.html", ctx)
        
        # Browser normal → página completa com layout
        return await render("users/list.html", ctx)
```

### htmx response headers

```python
@post("/users", status=201)
async def create_user(
    self,
    body: Annotated[CreateUserDTO, Body()],
) -> HtmlResponse:
    user = await self.service.create(body)
    
    response = await render("partials/user_row.html", {"user": user})
    
    # Controlar comportamento htmx via headers
    response.htmx\
        .trigger("userCreated")\          # dispara evento JS
        .push_url(f"/users/{user.id}")\   # atualiza URL no browser
        .retarget("#user-list")            # muda o alvo do swap
    
    return response
```

### Exemplo completo: CRUD com htmx

**Controller**:
```python
class TaskController:
    def __init__(self, service: TaskService) -> None:
        self.service = service

    @html("/tasks")
    async def index(self, request: AuraRequest) -> HtmlResponse:
        tasks = await self.service.list()
        ctx = TaskListContext(tasks=tasks, total=len(tasks))
        if request.htmx.is_htmx:
            return await render("partials/task_list.html", ctx)
        return await render("tasks/index.html", ctx)

    @post("/tasks")
    async def create(
        self, body: Annotated[CreateTaskDTO, Body()]
    ) -> HtmlResponse:
        task = await self.service.create(body)
        response = await render("partials/task_item.html", {"task": task})
        response.htmx.trigger("taskCreated")
        return response

    @delete("/tasks/{id}")
    async def delete(self, id: Annotated[int, Param()]) -> HtmlResponse:
        await self.service.delete(id)
        return HtmlResponse("")  # htmx remove o elemento do DOM
```

**Template** (`templates/tasks/index.html`):
```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://unpkg.com/htmx.org@2"></script>
</head>
<body>

  {# Form via htmx — sem reload #}
  <form hx-post="/tasks"
        hx-target="#task-list"
        hx-swap="beforeend"
        hx-on:htmx:after-request="this.reset()">
    <input name="title" placeholder="Nova tarefa" required>
    <button type="submit">Adicionar</button>
  </form>

  {# Lista que recebe os fragmentos #}
  <ul id="task-list">
    {% include "partials/task_list.html" %}
  </ul>

</body>
</html>
```

**Partial** (`templates/partials/task_item.html`):
```html
<li id="task-{{ task.id }}" hx-target="this">
  <span>{{ task.title }}</span>
  <button hx-delete="/tasks/{{ task.id }}"
          hx-swap="outerHTML swap:300ms">
    🗑
  </button>
</li>
```

---

## Alpine.js — estado local sem build

Para interatividade puramente local (modal, tabs, dropdown), use Alpine.js junto com htmx:

```html
{# Modal controlado por Alpine.js #}
<div x-data="{ open: false }">
  <button @click="open = true">Abrir</button>

  <div x-show="open" x-transition>
    <h2>Confirmar exclusão</h2>
    <button @click="open = false">Cancelar</button>
    <button hx-delete="/tasks/{{ task.id }}"
            hx-swap="outerHTML"
            @click="open = false">
      Confirmar
    </button>
  </div>
</div>
```

```html
{# Tabs com Alpine — sem servidor #}
<div x-data="{ tab: 'active' }">
  <button @click="tab = 'active'" :class="{ active: tab === 'active' }">Ativas</button>
  <button @click="tab = 'done'"   :class="{ active: tab === 'done' }">Concluídas</button>

  <div x-show="tab === 'active'"
       hx-get="/tasks?status=active"
       hx-trigger="revealed">
  </div>
  <div x-show="tab === 'done'"
       hx-get="/tasks?status=done"
       hx-trigger="revealed">
  </div>
</div>
```

---

## Islands Architecture — ilhas JS em HTML estático

Para páginas que são principalmente estáticas mas têm seções interativas (dashboard, gráficos, chat):

```python
class DashboardContext(TemplateContext):
    # Dados estáticos — renderizados no servidor
    stats: StatsResponse
    recent_orders: list[OrderSummary]
    # Ilhas interativas — props serializadas para JS
    chart_island: IslandProps
    notifications_island: IslandProps

class IslandProps(TemplateContext):
    """Props de um componente JS hidratado no cliente."""
    component: str         # nome do componente JS
    props: dict            # dados passados ao componente
    eager: bool = False    # carregar imediatamente ou lazy

@html("/dashboard")
async def dashboard(self) -> HtmlResponse:
    return await render("dashboard.html", DashboardContext(
        stats=await self.service.get_stats(),
        recent_orders=await self.service.recent_orders(limit=5),
        chart_island=IslandProps(
            component="SalesChart",
            props={"endpoint": "/api/sales/weekly"},
        ),
        notifications_island=IslandProps(
            component="NotificationFeed",
            props={"wsUrl": "/ws/notifications"},
            eager=True,
        ),
    ))
```

**Template** (`templates/dashboard.html`):
```html
{# Seções estáticas — puro HTML, sem JS #}
<section class="stats">
  <div class="stat">{{ stats.total_revenue | money }}</div>
  <div class="stat">{{ stats.active_users }}</div>
</section>

<section class="recent-orders">
  {% for order in recent_orders %}
    {{ component("order_row", order=order) }}
  {% endfor %}
</section>

{# Ilhas interativas — apenas estas hidratam JS #}
<div data-island="{{ chart_island.component }}"
     data-props="{{ chart_island.props | tojson }}"
     data-eager="{{ chart_island.eager | lower }}">
</div>

<div data-island="{{ notifications_island.component }}"
     data-props="{{ notifications_island.props | tojson }}"
     data-eager="{{ notifications_island.eager | lower }}">
</div>

{# Script mínimo para hidratar as ilhas #}
<script src="/js/islands.js"></script>
```

---

## Server-Sent Events (SSE)

Para atualizações em tempo real sem WebSocket (feed, notificações, progresso):

```python
from aura.templates import sse
import asyncio

class NotificationController:
    @sse("/events/notifications")
    async def notifications_stream(self, request: AuraRequest):
        """Stream de notificações em tempo real."""
        user_id = request.user.id
        async for event in notification_bus.subscribe(user_id):
            yield {
                "type": event.type,
                "message": event.message,
                "timestamp": event.created_at.isoformat(),
            }

    @sse("/events/export-progress/{job_id}")
    async def export_progress(
        self,
        job_id: Annotated[str, Param()],
    ):
        """Progresso de uma exportação longa."""
        while True:
            progress = await job_tracker.get_progress(job_id)
            yield {"percent": progress.percent, "status": progress.status}
            if progress.done:
                break
            await asyncio.sleep(0.5)
```

**Template com SSE**:
```html
<div id="notifications"></div>

<script>
  const source = new EventSource("/events/notifications");
  source.onmessage = (event) => {
    const data = JSON.parse(event.data);
    document.getElementById("notifications").innerHTML += `
      <div class="notification">${data.message}</div>
    `;
  };
</script>
```

---

## Testando templates

### Testando o contexto (sem render)

```python
async def test_user_list_context():
    users = [UserResponse(id=1, name="Alice", email="alice@example.com")]
    ctx = UserListContext(users=users, total=1, page=1, page_size=10)
    
    assert ctx.total_pages == 1
    assert ctx.has_next is False
    assert ctx.users[0].name == "Alice"

async def test_context_validation_fails():
    with pytest.raises(ValidationError):
        # total é obrigatório
        UserListContext(users=[], page=1)
```

### Testando componentes (sem HTTP)

```python
async def test_user_card_renders():
    user = UserResponse(id=1, name="Bob", email="bob@example.com")
    engine = AuraTemplateEngine(template_dirs=["templates"])
    
    html = await UserCard(engine).render(UserCardProps(user=user, show_email=True))
    
    assert "Bob" in html
    assert "bob@example.com" in html

async def test_user_card_hides_email():
    user = UserResponse(id=1, name="Bob", email="bob@example.com")
    engine = AuraTemplateEngine(template_dirs=["templates"])
    
    html = await UserCard(engine).render(UserCardProps(user=user, show_email=False))
    
    assert "Bob" in html
    assert "bob@example.com" not in html
```

### Testando rotas HTML com TestClient

```python
from aura.testing import TestClient

client = TestClient(app)

def test_user_list_page():
    response = client.get("/users")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "All Users" in response.text

def test_htmx_partial():
    response = client.get("/users", headers={"HX-Request": "true"})
    assert response.status_code == 200
    # Partial não inclui layout
    assert "<html>" not in response.text
    assert "<li" in response.text  # mas tem os items
```

---

## Comparação com Django

| Feature | Django | Aura |
|---|---|---|
| Context type-safe | ❌ dict livre | ✅ Pydantic TemplateContext |
| Validação antes de render | ❌ nenhuma | ✅ automática |
| IDE support no context | ❌ | ✅ |
| Sistema de componentes | ⚠️ include + macros | ✅ Component classes |
| Props validadas | ❌ | ✅ Pydantic |
| N+1 prevention | ❌ (armadilha fácil) | ✅ context em Python |
| htmx integration | ❌ manual | ✅ `request.htmx` |
| htmx response headers | ❌ manual | ✅ `response.htmx.trigger()` |
| SSE | ❌ biblioteca externa | ✅ `@sse` decorator |
| Hot reload templates | ⚠️ runserver | ✅ `auto_reload=True` |
| Testabilidade | ⚠️ render HTML completo | ✅ testar context + component isolados |
| Alpine.js friendly | ✅ | ✅ |

---

## Referência rápida

```python
# Instalar
pip install "aura-web[templates]"

# Configurar
AuraTemplateModule.for_root("templates", auto_reload=True)

# Renderizar
await render("page.html", MyContext(title="..."))

# Detectar htmx
if request.htmx.is_htmx: ...

# Responder com htmx headers
response.htmx.trigger("eventName").push_url("/path")

# Componente em template
{{ component("user_card", user=user, show_email=True) }}

# Arquivo estático
{{ static("css/app.css") }}

# SSE
@sse("/events/feed")
async def feed(self):
    async for item in stream:
        yield {"data": item}
```

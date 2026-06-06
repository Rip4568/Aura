/**
 * docs-data.js
 * 
 * Comprehensive, exhaustive, and highly educational documentation dataset for the Aura Framework.
 * Exported as an ES module to be loaded dynamically on the Aura Landing Page.
 */

window.docsData = {
  version: "1.0.0",
  lastUpdated: "2026-06-02",
  sections: [
    {
      id: "introduction-motivation",
      title: "1. Introduction & Motivation",
      summary: "A high-level architectural overview of Aura's async-first design and the concrete real-world framework issues it was built to solve.",
      markdown: `# Introduction & Motivation: The Async-First Evolution

## 1.1 The Paradigm Clash in Python Web Development
Between 2024 and 2026, Python's backend ecosystem faced a structural tension:
- **Django** remains "batteries included" but relies on architectural patterns conceived in 2005. Its legacy core makes asynchronous operations complex, verbose, and performatively expensive.
- **FastAPI** is highly modern and type-safe but delivers "no batteries," forcing teams to design their own project structure, database lifecycle managers, and background job adapters, which often leads to inconsistent and fragile boilerplate architectures.
- **Flask** is lightweight and unopinionated, but this complete freedom frequently transforms large, enterprise-grade projects into unmaintainable, circular-import-ridden codebases.

**Aura** was engineered to resolve these issues. It offers a highly structured, **async-first, NestJS-inspired modular architecture** with first-class type safety via **Pydantic v2**, a native dependency injection container, real asynchronous ORM management via **SQLAlchemy 2.x**, and background job queues powered by **SAQ**.

---

## 1.2 Concrete Pain Points & How Aura Eliminates Them

### 1.2.1 Django's Bloated settings.py
In large Django projects, \`settings.py\` grows into an unmanageable, untyped file of hundreds of lines.
- **The Issue:** Environment variables (via \`django-environ\` or \`python-decouple\`) lack strict startup validation. A typo or missing key like \`DATABASE_URL\` is often only discovered at runtime or in production. Configurations for entirely different modules are forced into a single global namespace, breaking modularity and causing constant git merge conflicts.
- **The Solution:** Aura separates configurations using a strictly typed, modular \`aura.toml\` file, validated at startup via Pydantic models.

\`\`\`toml
# aura.toml
[app]
name = "My High Performance API"
secret_key = "\${SECRET_KEY}"  # Fails at startup if environment variable is missing

[database]
url = "\${DATABASE_URL}"
pool_size = 15

[jobs]
backend = "saq"
broker_url = "\${REDIS_URL}"
\`\`\`

---

### 1.2.2 Django REST Framework (DRF) Performance Bottlenecks
DRF's \`ModelSerializer\` is heavily overloaded: it is simultaneously a validator, a response builder, and a location for database query triggers.
- **The Issue:** DRF is notoriously slow due to excessive reflection and serialization overhead. In community-verified benchmarks, serializing 5,000 model instances with \`ModelSerializer\` takes **12.8 seconds**, whereas a plain Python function performs the same serialization in **0.034 seconds** (making DRF **377x slower**). Additionally, nested serializers easily trigger severe **N+1 query** problems by default.
- **The Solution:** Aura separates concerns completely. It uses **Pydantic v2** for ultra-fast, C-optimized validation and serialization, coupled with explicit **Repository** contracts. Lógica de negócio belongs to the *Service*, serialization contract to the *Schema*, and HTTP delivery to the *Controller*.

\`\`\`python
# Schema (Strictly typed data transfer contract)
class UserResponse(Schema):
    id: int
    name: str
    email: EmailStr
    is_active: bool

# Controller (Zero business logic, handles request/response lifecycle)
class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @get("/users/{id}")
    async def get_user(self, id: int) -> UserResponse:
        user = await self.service.get_by_id(id)
        return UserResponse.model_validate(user)  # 300x faster than DRF!
\`\`\`

---

### 1.2.3 Django's Pseudo-Async ORM
Django introduced async views and async ORM capabilities recently, but the underlying implementation is not truly asynchronous.
- **The Issue:** Under the hood, Django wraps synchronous database calls using thread pools (via \`sync_to_async\`). This prevents genuine asynchronous connection pooling, introduces context switching overhead, and risks blocking the event loop. Worse, accessing lazy-loaded relationships on a model (e.g., \`user.profile\`) in an async context silently throws synchronous block errors.
- **The Solution:** Aura utilizes **SQLAlchemy 2.x async** as its primary engine, executing natively asynchronous database drivers (like \`asyncpg\` or \`aiosqlite\`) without any thread-pool wrappers, enforcing explicit eager loading.

---

### 1.2.4 FastAPI's Request-Bound Dependency Injection
FastAPI offers dependency injection through \`Depends()\`, but it has a fundamental design limitation.
- **The Issue:** FastAPI's DI is tightly coupled to the HTTP request lifecycle. You can inject a service into a route controller, but you **cannot** reuse that same injection setup inside a Celery background job, a CLI command, or an offline script. This leads to duplicate instantiation code and database session management boilerplate.
- **The Solution:** Aura's DI container is completely decoupled from the HTTP layer. Registered dependencies can be resolved anywhere—in HTTP routers, background workers, tests, or CLI commands.

\`\`\`python
# Aura Service resolved dynamically in a worker background task
@task(queue="emails")
async def send_welcome_email(user_id: int, mailer: EmailService):
    # 'mailer' is automatically resolved from the same DI container used by the HTTP endpoints!
    await mailer.send_user_welcome(user_id)
\`\`\`

---

### 1.2.5 Celery's Outdated Architecture
Celery has been the standard for Python task queues, but it carries legacy weight.
- **The Issue:** Celery is not async-native, requiring complex event-loop wrappers inside tasks to call async APIs. By default, it uses **acknowledge-early**, acknowledging tasks *before* execution; if a worker crashes mid-task, that job is lost forever. Setting up Celery requires dozens of cryptic parameters, and the monitoring tool (Flower) is non-persistent by default.
- **The Solution:** Aura integrates **SAQ (Simple Async Queue)**. It is entirely async-native, runs on the same event loop, uses **late-acknowledgement (pessimistic execution)** so jobs are never lost, and features exponential backoff retries and an integrated real-time monitoring dashboard with zero additional setup.

---

## 1.3 Architectural Comparison Matrix

| Architectural Feature | Django & DRF | FastAPI | Aura Framework |
| :--- | :--- | :--- | :--- |
| **Primary Execution Model** | Synchronous (Async is wrapped) | Asynchronous | **Truly Asynchronous (Async-First)** |
| **Dependency Injection** | None (Service Locator patterns) | Partial (Only in HTTP routes via \`Depends\`) | **Full (Injected in Controllers, Services, Jobs, CLI, Seeders)** |
| **Modularity & Structure** | Legacy App structure (Loose) | None (Developer must invent) | **Strict, Scalable Modular Registry (\`@Module\`)** |
| **ORM Async Capability** | Thread-pool wrapped (\`sync_to_async\`) | Manual configurations | **Native Async (SQLAlchemy 2.x + Repository pattern)** |
| **Serialization Speed** | ❌ Very Slow (DRF Serializers) | ✅ Fast (Pydantic v1/v2) | 🔥 **Ultra Fast (Pydantic v2 C-compiled validation)** |
| **Job Queue Integration** | Heavy external setup (Celery) | Manual task setup required | **Native SAQ Async Queue (Redis / Memory)** |
| **Startup Configurations** | Untyped, global \`settings.py\` | Manual Pydantic settings | **Strictly typed, modularized \`aura.toml\`** |
| **Admin Panel** | Included (Synchronous, legacy CSS) | None (Requires 3rd party) | **Included (Async, HTMX, Tailwind, dynamic forms reflection)** |
| **Spec-Driven Design (SDD)**| No first-class support | Partial (via OpenAPI) | **First-class integration (LLM-friendly schemas & modules)** |`
    },
    {
      id: "dependency-injection",
      title: "2. Modularity & Dependency Injection (DI)",
      summary: "In-depth breakdown of Aura's NestJS-inspired module registry and type-safe DI container.",
      markdown: `# Dependency Injection & Modularity

## 2.1 The Philosophy of Structured Modularity
Large projects in Flask and FastAPI often suffer from circular imports, untestability, and code scattered across unorganized files. Aura resolves this by imposing a **modular architecture** inspired by NestJS. 

A **Module** serves as a boundary that encapsulates related features (controllers, services, repositories, and models). Nothing inside a module is visible to the rest of the application unless it is explicitly listed in the \`exports\` array.

```
       [ AppModule (Root) ]
      /                    \\
[ UserModule ] ----> [ AuthModule ]
  (Imports Auth)       (Exports AuthService)
```

---

## 2.2 Deep Dive into `@Module` Architecture

Every feature in Aura is organized around a module class decorated with \`@Module()\`.

\`\`\`python
# modules/users/module.py
from aura import Module
from .controller import UserController
from .service import UserService
from .repository import UserRepository

@Module(
    imports=[],                                # External modules needed inside this module
    providers=[UserRepository, UserService],   # Services and Repositories available for injection
    controllers=[UserController],              # HTTP Controllers that handle requests
    exports=[UserService],                     # Injected classes made available to importing modules
    prefix="/users",                           # Route prefix for all controllers in this module
    tags=["Users Management"],                 # OpenAPI group tags
    guards=[]                                  # Module-level security guards
)
class UserModule:
    """The UserModule encapsulates all resources related to User management."""
    pass
\`\`\`

### Module Parameters Explained:
1. **\`imports\`**: Lists other modules whose exported providers should be available inside this module's container scope.
2. **\`providers\`**: Classes decorated with \`@injectable\` that the DI container instantiates and manages within this module.
3. **\`controllers\`**: Route handler classes. They are instantiated by the module and registered with the Starlette HTTP router.
4. **\`exports\`**: A subset of providers that other modules will get access to when they list this module in their \`imports\`.
5. **\`prefix\`**: Prepended to every route path inside the controllers of this module.
6. **\`guards\`**: Execution controllers that run before any route in the module is executed to handle authorization.

---

## 2.3 Injectable Lifetimes & State Retention
Aura offers three distinct lifecycles for injected classes, configured via the \`lifetime\` parameter on the \`@injectable\` decorator:

| Lifetime | Instantiation Pattern | Ideal Use Cases |
| :--- | :--- | :--- |
| **\`SINGLETON\`** (Default) | Single global instance shared across the entire app execution. | Configuration managers, HTTP Clients, Database connection pools, Stateless services. |
| **\`SCOPED\`** | One instance created per execution context (e.g., HTTP request, background task). | Request logs, tenant context, database transactions (Unit of Work). |
| **\`TRANSIENT\`** | A fresh instance is created every single time it is resolved. | Heavy-computation builders, formatters, and stateless lightweight helpers. |

\`\`\`python
from aura import injectable, Lifetime

# Singleton (1 instance per application lifetime)
@injectable
class ConfigService:
    def __init__(self):
        self.app_env = "production"

# Scoped (1 instance per HTTP Request / Worker Task execution)
@injectable(lifetime=Lifetime.SCOPED)
class RequestTracker:
    def __init__(self):
        self.trace_id = uuid.uuid4().hex
        self.logs = []

# Transient (A new instance for every injection request)
@injectable(lifetime=Lifetime.TRANSIENT)
class PDFGenerator:
    def build_report(self, data: dict):
        pass
\`\`\`

---

## 2.4 Explaining Explicit Injection with `@inject` and `Annotated`
Aura uses standard Python type hints inside the \`__init__\` constructor to automatically resolve dependencies. However, there are scenarios where you want to explicitly direct the resolver—such as when injecting a dependency registered under a custom string name instead of a class, or when swapping implementations.

Aura provides the \`inject\` helper to accomplish this:

\`\`\`python
from typing import Annotated
from aura import injectable, inject
from .interfaces import MessageSender

@injectable
class OrderService:
    def __init__(
        self,
        # Explicitly instruct DI to inject the class registered under the name "SmsSender"
        sender: Annotated[MessageSender, inject("SmsSender")],
        tracker: Annotated[RequestTracker, inject()] # Explicit typing decorator (optional)
    ):
        self.sender = sender
        self.tracker = tracker
\`\`\`

---

## 2.5 Dynamic Container Registration
You can also register and resolve services programmatically using \`DIContainer\`. This is highly useful for testing or boot scripts.

\`\`\`python
from aura.di.container import DIContainer

# 1. Initialize the container
container = DIContainer()

# 2. Register an injectable class
container.register(UserService)

# 3. Register a pre-constructed instance (e.g., mock configurations)
app_config = AppConfig(debug=True)
container.register_instance(AppConfig, app_config)

# 4. Register a dynamic factory function
container.register_factory(
    DatabaseSession, 
    lambda: AsyncSession(engine), 
    lifetime=Lifetime.SCOPED
)

# 5. Programmatic Resolution
user_service = await container.resolve(UserService)
\`\`\`

---

## 2.6 Lifecycle Context Boundaries
The DI Container behaves differently depending on the application runtime boundary:
1. **HTTP Request Boundary:** The HTTP server creates an isolated container **Scope** on every incoming request. Providers registered with \`Lifetime.SCOPED\` are instantiated once for this request, sharing the database session, and are garbage-collected once the response is sent.
2. **Background Jobs Boundary:** Each SAQ worker thread creates a scoped execution context when it picks up a task, providing job-level database isolated sessions.
3. **CLI Commands Boundary:** Commands executing in the terminal construct their own isolated container context and release it upon command termination.

---

## 2.7 Complete Functional Example: User Registration Flow

Here is a complete, real-world flow showing a controller, a service, a repository, and a module interacting together with full constructor injections.

\`\`\`python
# 1. Define the User Repository (modules/users/repository.py)
from aura.orm.repository import Repository
from .models import User
from aura import injectable, Lifetime

@injectable(lifetime=Lifetime.SCOPED)
class UserRepository(Repository[User]):
    model = User  # Connects directly to the User AuraModel
    
    async def find_by_email(self, email: str) -> User | None:
        # Custom query returning the model or None
        return await User.objects.first(email=email)

# 2. Define the User Service (modules/users/service.py)
from aura import injectable
from aura.exceptions import ConflictException
from .repository import UserRepository
from .schemas import CreateUserDTO
from .models import User

@injectable
class UserService:
    # Constructor Injection: The container automatically resolves UserRepository
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register_new_user(self, dto: CreateUserDTO) -> User:
        # Check if user already exists
        existing = await self.user_repo.find_by_email(dto.email)
        if existing:
            raise ConflictException("Email address is already in use.")
            
        # Create and persist model
        return await self.user_repo.create(
            name=dto.name,
            email=dto.email,
            password_hash=hash_password(dto.password)
        )

# 3. Define the HTTP Controller (modules/users/controller.py)
from aura import post, Body
from .service import UserService
from .schemas import CreateUserDTO, UserResponse

class UserController:
    # Constructor Injection: The container automatically resolves UserService
    def __init__(self, user_service: UserService):
        self.user_service = user_service

    @post("/register", status=201)
    async def create_user(self, body: Body[CreateUserDTO]) -> UserResponse:
        user = await self.user_service.register_new_user(body)
        return UserResponse.model_validate(user)

# 4. Register inside the Module (modules/users/module.py)
from aura import Module

@Module(
    providers=[UserRepository, UserService],
    controllers=[UserController],
    exports=[UserService],
    prefix="/users",
    tags=["Users"]
)
class UserModule:
    pass
\`\`\`

### Line-by-Line Code Explanation:
- **Repository Definition (\`repository.py\`)**:
  - **Line 5**: \`@injectable(lifetime=Lifetime.SCOPED)\` marks the repository as injectable with a \`SCOPED\` lifetime. A new repository is created for each HTTP request, ensuring it uses the same database session as other scoped services during that request.
  - **Line 6**: Inheriting from \`Repository[User]\` grants this class pre-built CRUD methods (\`get\`, \`list\`, \`create\`, \`delete\`).
  - **Line 7**: \`model = User\` associates the repository with the SQLAlchemy \`User\` model.
  - **Line 10**: \`User.objects.first(email=email)\` uses AuraQL to fetch a single user matching the email.
- **Service Definition (\`service.py\`)**:
  - **Line 7**: \`@injectable\` registers this service as a singleton (default).
  - **Line 10**: \`def __init__(self, user_repo: UserRepository)\` receives \`UserRepository\`. The container detects this type hint and resolves the instance automatically.
  - **Line 14**: Checks if the user already exists. If yes, it raises a \`ConflictException\` which returns an HTTP 409 error.
  - **Line 18**: \`self.user_repo.create(...)\` persists the new user to the database.
- **Controller Definition (\`controller.py\`)**:
  - **Line 7**: \`def __init__(self, user_service: UserService)\` receives the service instance via constructor injection.
  - **Line 10**: \`@post("/register", status=201)\` registers a POST route at \`/users/register\` that returns a 201 Created status.
  - **Line 11**: \`body: Body[CreateUserDTO]\` specifies that the request body will be validated against \`CreateUserDTO\` (Pydantic v2).
  - **Line 13**: \`UserResponse.model_validate(user)\` serializes the ORM user model into the output DTO.
- **Module Definition (\`module.py\`)**:
  - **Line 3**: The \`@Module\` decorator binds the controller and providers together, defining the router prefix \`/users\` for all routes in this controller.
`
    },
    {
      id: "orm-querybuilder",
      title: "3. Database ORM, AuraQL & Data Seeding",
      summary: "Comprehensive guide to Aura's async ORM, fluent AuraQL query builder, concurrency management, model factories, and robust data seeders.",
      markdown: `# Asynchronous ORM, AuraQL, Factories & Data Seeding

## 3.1 Defining Database Models with \`AuraModel\`
Aura uses an asynchronous layer on top of **SQLAlchemy 2.x**. Instead of using raw SQLAlchemy syntax, you inherit from \`AuraModel\`.

\`\`\`python
from aura.orm import AuraModel, CharField, EmailField, BooleanField, TextField, ForeignKey
from sqlalchemy.orm import Mapped, relationship

class User(AuraModel):
    __tablename__ = "users"

    name: Mapped[str] = CharField(max_length=100)
    email: Mapped[str] = EmailField(unique=True, index=True)
    is_active: Mapped[bool] = BooleanField(default=True)
    
    # Relationship definition
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="author", cascade="all, delete-orphan")

class Post(AuraModel):
    __tablename__ = "posts"

    title: Mapped[str] = CharField(max_length=200)
    content: Mapped[str] = TextField()
    
    # Foreign key binding and cascade rules
    author_id: Mapped[int] = ForeignKey("users.id", ondelete="CASCADE")
    author: Mapped["User"] = relationship("User", back_populates="posts")
\`\`\`

### Attributes Automatically Provided by \`AuraModel\`:
Every model inheriting from \`AuraModel\` automatically gets three fields, eliminating repetitive column declarations:
1. **\`id\`**: Primary Key, auto-increment integer (\`Mapped[int]\`).
2. **\`created_at\`**: UTC timestamp set automatically on record insertion.
3. **\`updated_at\`**: UTC timestamp updated automatically on record modification.

---

## 3.2 Programmatic Database Operations with \`Repository[T]\`
The Repository Pattern decouples your data layer from your business logic. By inheriting from \`Repository[T]\`, you instantly gain a robust, asynchronous CRUD interface.

\`\`\`python
from aura.orm.repository import Repository
from .models import User

class UserRepository(Repository[User]):
    model = User  # Bind this repository to the User AuraModel
\`\`\`

### Comprehensive List of CRUD Operations:

| Method Syntax | Return Value | Internal Database Operation |
| :--- | :--- | :--- |
| **\`await repo.get(id)\`** | \`ModelT \| None\` | Fetches a single record by its Primary Key; returns None if not found. |
| **\`await repo.get_or_raise(id)\`** | \`ModelT\` | Fetches by Primary Key; raises a 404 \`NotFoundException\` if missing. |
| **\`await repo.list(limit=50, offset=0, order_by="-created_at", **filters)\`** | \`list[ModelT]\` | Returns a list of records supporting pagination, sorting, and field filtering. |
| **\`await repo.create(**fields)\`** | \`ModelT\` | Inserts a new record, flushes the session, and returns the persisted object with its ID. |
| **\`await repo.update(id, **fields)\`** | \`ModelT\` | Updates specified columns on a record. Raises a 404 if the record does not exist. |
| **\`await repo.delete(id)\`** | \`bool\` | Deletes a record by ID. Returns True if deleted, False if the record wasn't found. |
| **\`await repo.exists(**filters)\`** | \`bool\` | Performs a fast existence check (\`EXISTS\` query) based on filters. |
| **\`await repo.count(**filters)\`** | \`int\` | Returns the count of matching records. |
| **\`await repo.first(**filters)\`** | \`ModelT \| None\` | Returns the first record matching the filters, or None. |
| **\`await repo.bulk_create(list_of_dicts)\`** | \`list[ModelT]\` | Performs a bulk insert, optimizing database round-trips. |

---

## 3.3 Fluent Querying via AuraQL
AuraQL is an advanced, developer-focused query builder integrated directly into your models via the \`objects\` manager. It supports complex lookups, conditional filtering, and Prisma-style relation inclusion.

\`\`\`python
from aura.orm import Q
from .models import User

# Complex search using OR, filtering, sorting and eager loading relationships
users = await (
    User.objects
    .filter(
        Q(name__icontains="John") | Q(email__endswith="@aura.dev"),
        is_active=True
    )
    .include("posts")  # Eager loading: loads user posts in a single query
    .order_by("-created_at")
    .limit(10)
    .all()
)
\`\`\`

### Relation Loaders: `include()` vs `select_related()`
- **\`include("posts")\`**: Used for one-to-many or many-to-many relationships. It triggers SQLAlchemy's \`selectinload\` strategy, loading related records in a single optimized secondary query. This completely solves the N+1 query problem.
- **\`select_related("author")\`**: Used for foreign key relationships (many-to-one). It performs a SQL \`JOIN\`, fetching both records in a single query.

---

## 3.4 Safe Asynchronous Concurrency with `db.parallel`
SQLAlchemy's \`AsyncSession\` is not thread-safe and **cannot** execute multiple concurrent queries on the same connection. If you attempt to use \`asyncio.gather\` with the same session, it will fail:

\`\`\`python
# ❌ THIS WILL FAIL WITH A CONCURRENCY ERROR IN SQLALCHEMY
async def get_dashboard_data():
    # Attempting concurrent operations on the same session causes crashes
    users_task = repo.list(limit=5)
    count_task = repo.count()
    return await asyncio.gather(users_task, count_task) 
\`\`\`

To solve this developer experience bottleneck, Aura provides the \`db.parallel\` helper. It automatically allocates separate connections from the database pool for each task, executes them concurrently, and aggregates the results:

\`\`\`python
# ✅ THE AURA WAY: SAFE CONCURRENT QUERIES
from aura.orm.session import db

async def get_dashboard_data(self) -> dict:
    # Safely executes queries in parallel using independent pool connections
    recent_users, total_users = await db.parallel(
        lambda s: UserRepository(s).list(limit=5, order_by="-created_at"),
        lambda s: UserRepository(s).count()
    )
    return {
        "recent_users": recent_users,
        "total_users": total_users
    }
\`\`\`

---

## 3.5 Model Factories & The "Partial Attribute Override" Feature
Aura features a highly expressive testing and seeding tool called **Model Factories**, which integrate seamlessly with the **Faker** library.

\`\`\`python
from aura.orm import Factory
from .models import User

class UserFactory(Factory[User]):
    model = User

    def definition(self) -> dict:
        return {
            "name": lambda: self.faker.name(),
            "email": lambda: self.faker.unique.email(),
            "is_active": True
        }
\`\`\`

### Gering Strategies: In-Memory vs. Database Persistence
1. **In-Memory Gering (Ultra Fast - No Database I/O):**
   - \`make(**overrides)\`: Returns a single model instance.
   - \`make_many(count, **overrides)\`: Returns a list of instances.
2. **Database Persistence (Asynchronous I/O):**
   - \`await create(**overrides)\`: Persists a model instance.
   - \`await create_many(count, **overrides)\`: Persists a list of instances within a single transaction.

### Explain the "Partial Attribute Override" Feature:
When generating data using a factory, you can pass explicit overrides for specific fields. Aura uses **Partial Attribute Override**: any field you pass explicitly is set exactly as requested, while all unspecified fields are generated dynamically on-the-fly using the factory's default definitions (like Faker lambdas).

\`\`\`python
# 1. Standard Faker generation
user_1 = UserFactory().make()
# name: "Jane Doe" (Faker), email: "jane@example.com" (Faker), is_active: True

# 2. Overriding only the name
user_2 = UserFactory().make(name="Alice")
# name: "Alice" (Override), email: "alice_generated@example.com" (Faker), is_active: True

# 3. Overriding only the email
user_3 = UserFactory().make(email="bob@example.com")
# name: "Bob Miller" (Faker), email: "bob@example.com" (Override), is_active: True
\`\`\`

### Encapsulating Factory States with `.state()`
Fairy states allow you to chain variations of a model immutably:

\`\`\`python
# Define states using .state()
admin_factory = UserFactory().state(is_admin=True)
inactive_admin_factory = admin_factory.state(is_active=False)

# Instantiation does not affect the root factory
admin = admin_factory.make()            # is_admin=True, is_active=True
inactive = inactive_admin_factory.make() # is_admin=True, is_active=False
\`\`\`

---

## 3.6 Relationships with `SubFactory` & Contextual Transactions
Generating related records in async databases often triggers \`DetachedInstanceError\` errors or uses too many connections from the pool. Aura solves this using a **ContextVar**-based session manager (\`current_session\`) and \`SubFactory\`.

When you run a parent factory's \`create()\` method, Aura registers the transaction in \`current_session\`. Nested \`SubFactory\` instances automatically detect and reuse this active session, flushing changes to fetch foreign keys without committing early.

\`\`\`python
class PostFactory(Factory[Post]):
    model = Post

    def definition(self) -> dict:
        return {
            "title": lambda: self.faker.sentence(),
            "content": lambda: self.faker.paragraph(),
            # Automatically generates a User and assigns author_id
            "author": SubFactory(UserFactory)
        }

# Executing this creates a User and a Post in a single, safe transaction!
post = await PostFactory().create(title="Aura Asynchronous Power")
assert post.author.id == post.author_id
\`\`\`

---

## 3.7 Structured Data Seeders with Dependency Injection
Seeders populate the database with initial or mock data. Every Seeder in Aura is an \`@injectable\` class, meaning it can receive repositories or services via constructor injection.

\`\`\`python
# database/seeders/user_seeder.py
from aura.orm import Seeder
from modules.users.repository import UserRepository
from database.factories import UserFactory

class UserSeeder(Seeder):
    # Dependency Injection works out-of-the-box in seeders!
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def run(self) -> None:
        # Create administrative account programmatically
        if not await self.user_repo.exists(email="admin@aura.dev"):
            await UserFactory().create(
                name="Admin Manager", 
                email="admin@aura.dev", 
                is_admin=True
            )
        
        # Create standard test accounts
        await UserFactory().create_many(15)
\`\`\`

### Orchester Seeders in Chain with `self.call()`
You can run multiple seeders in order using the main \`DatabaseSeeder\`:

\`\`\`python
# database/seeders/main_seeder.py
from aura.orm import Seeder
from .user_seeder import UserSeeder
from .post_seeder import PostSeeder

class DatabaseSeeder(Seeder):
    async def run(self) -> None:
        # Execute sub-seeders in order
        await self.call([
            UserSeeder,
            PostSeeder
        ])
\`\`\`

### Running Seeders via CLI
\`\`\`bash
# Run the default DatabaseSeeder
aura db seed

# Run a specific seeder class
aura db seed --class UserSeeder

# Run idempotently (registers ran seeders in the _aura_seeded table to prevent duplicate runs)
aura db seed --once
\`\`\`

---

## 3.8 Production Fail-Safe Protection
Running seeders in production can lead to accidental data loss. Aura provides a robust fail-safe mechanism:

If the framework detects a production environment (via \`AURA_ENV=production\`, \`ENV=production\`, or by finding \`prod\` or \`production\` keywords in the database URL), it pauses execution, displays a high-contrast warning in the terminal, and prompts for manual operator confirmation:

\`\`\`text
┌─────────────────────────────── Production Alert ───────────────────────────────┐
│ WARNING: You are running in a PRODUCTION environment!                          │
└────────────────────────────────────────────────────────────────────────────────┘
Are you sure you want to run the database seeders? [y/N]: 
\`\`\`
If the operator enters anything other than \`y\`, the process aborts immediately, keeping your production data safe.
`
    },
    {
      id: "admin-dashboard",
      title: "4. Aura Admin: Dynamic Dashboard & Security",
      summary: "How to configure Aura Admin, register models with custom specifications, handle dynamic form reflection, and leverage HTMX reactivity and fail-closed security.",
      markdown: `# Aura Admin: Dynamic Dashboard & Security

## 4.1 Principles & Architecture
**Aura Admin** is an asynchronous, declaratively generated administration panel powered by your database models. Inspired by the simplicity of the Django Admin, it features a modern, responsive user experience built with **HTMX**, **Tailwind CSS**, and **Jinja2** templates.

```
Model Definition ---> ModelAdmin Inferred Schema ---> Jinja2 Form Generation
                                                             |
HTML Partial Swaps <--- HTMX Processing <--- Form Submits (HTMX Async POST)
```

---

## 4.2 Installation & Registration

### 4.2.1 Configuring the App Root Module
To enable the admin dashboard, register \`AdminModule.for_root()\` in your root module imports.

\`\`\`python
# app/module.py
from aura import Module
from aura.admin import AdminModule
from modules.users.module import UserModule

@Module(
    imports=[
        AdminModule.for_root(),  # Registers routes under the /admin prefix
        UserModule
    ]
)
class AppModule:
    pass
\`\`\`

### 4.2.2 Registering Models in Admin
You can register models with the admin panel in two ways:

#### Option A: Using the `@register` Decorator (Recommended)
\`\`\`python
# modules/users/admin.py
from aura.admin import ModelAdmin, register
from modules.users.models import User

@register(User)
class UserAdmin(ModelAdmin):
    list_display = ["id", "name", "email", "is_active", "created_at"]
    search_fields = ["name", "email"]
    list_filter = ["is_active"]
    ordering = ["-created_at"]
    per_page = 15
\`\`\`

#### Option B: Manual Registration
\`\`\`python
# modules/users/admin.py
from aura.admin import register_model
from modules.users.models import User

class UserAdmin(ModelAdmin):
    list_display = ["id", "name", "email"]

# Manual registration
register_model(User, UserAdmin)
\`\`\`

---

## 4.3 Customization Options in `ModelAdmin`
- **\`list_display\`**: Columns shown in the admin list view.
- **\`search_fields\`**: Enbles a search bar that queries the database using \`LIKE\` filters against these fields.
- **\`list_filter\`**: Adds sidebar filters for specific fields (e.g., filtering active/inactive status).
- **\`ordering\`**: The default sort order applied to the list view (e.g., \`["-id"]\` for descending).
- **\`per_page\`**: The number of records displayed per page (defaults to 20).

---

## 4.4 Dynamic Schema Reflection & Type Coercion
Under the hood, Aura Admin inspects your SQLAlchemy models to handle forms and validation automatically:

1. **Form Gering:** When you open the record creation or edit view, Aura Admin reads the column definitions from the database schema:
   - \`Boolean\` columns render as checkboxes.
   - \`Integer\` or \`Float\` columns render as number inputs.
   - \`DateTime\` and \`Date\` columns render as date-time picker inputs.
   - Foreign key relationships generate dropdown selectors pre-populated with related records.
   - Required columns (\`nullable=False\`) automatically get HTML \`required\` validations.
2. **Type Coercion and Validation:** When a form is submitted, the admin panel processes the input strings and converts them to their appropriate Python types (e.g., converting \`"on"\` to \`True\`, or strings to floats). If a database validation error occurs (like a duplicate email or missing value), the admin intercepts the exception and re-renders the form with field-specific errors, without a full page reload.

---

## 4.5 Production "Fail-Closed Security"
Aura Admin uses a **Fail-Closed Security** architecture to prevent accidental exposures in production.

If your application is running in production mode (\`AURA__DEBUG=false\` or similar) and the admin password environment variable (\`AURA_ADMIN_PASSWORD\` or \`AURA__ADMIN__PASSWORD\`) is not set, the framework **will refuse to start** and throws a \`RuntimeError\`:

\`\`\`python
# Internal auth check in views.py
def check_auth(self, request: AuraRequest):
    password = os.getenv("AURA_ADMIN_PASSWORD") or os.getenv("AURA__ADMIN__PASSWORD")
    if not password:
        is_debug = os.getenv("AURA__DEBUG", "true").lower() in ("true", "1")
        if not is_debug:
            raise RuntimeError(
                "AURA_ADMIN_PASSWORD must be configured in production environments (AURA__DEBUG=false) "
                "to secure the Administrative Panel. Please set the environment variable."
            )
        return None
\`\`\`

If a password is set, Aura Admin enforces login. If a user attempts to access any admin URL unauthorized, the system redirects them to the login page (\`/admin/login\`).

---

## 4.6 HTMX Reactivity & Micro-SPA Interactions
Instead of triggering slow, full-page reloads, Aura Admin uses **HTMX** to provide a fast, single-page application (SPA) experience:

- **Partial HTML Swapping:** When searching, filtering, or navigating pages, HTMX intercepts the request and sends an \`HX-Request: true\` header. The server detects this header and renders only the table body partial template (\`table_body.html\`) rather than the entire dashboard layout, reducing response sizes and speeding up rendering:

\`\`\`python
# Check for HTMX request inside the route handler
if request.htmx.is_htmx:
    return await render_admin("table_body.html", context)
return await render_admin("list.html", context)
\`\`\`

- **HTMX Trigger Headers:** When a record is successfully created, updated, or deleted, Aura Admin returns custom HTMX headers (like \`HX-Trigger: recordCreated\`) to trigger UI updates on the client:

\`\`\`python
# Triggering UI updates using HTMX headers
if request.htmx.is_htmx:
    response = HtmlResponse()
    response.htmx.trigger("recordCreated").redirect(f"/admin/{model_name.lower()}")
    return response
\`\`\`
`
    },
    {
      id: "background-jobs",
      title: "5. Background Jobs & Distributed Workers",
      summary: "How to configure Redis/Memory backends, write background tasks, schedule cron periodic routines, launch workers, and configure exponential backoffs.",
      markdown: `# Background Jobs & Distributed Workers

## 5.1 The Philosophy of Async Task Queues
Distributed background tasks are essential for responsive web applications. Aura integrates **SAQ (Simple Async Queue)** directly into its core, offering an async-first background processing engine. It runs on the same event loop, supports full dependency injection within task executions, and features late task acknowledgements to prevent data loss if a worker crashes.

---

## 5.2 Configuring Job Backends
Aura supports two background job backends, configured via your \`aura.toml\` file:

### 5.2.1 MemoryBackend (For Development and Testing)
The in-memory queue executes jobs in a background task on the same process. It is the default option and requires no configuration.

\`\`\`python
from aura.jobs.backends.memory import MemoryBackend

# The MemoryBackend handles local asynchronous concurrency
backend = MemoryBackend(concurrency=4)
await backend.startup()
\`\`\`

### 5.2.2 Redis / SAQ Backend (For Production)
The Redis backend persists tasks across restarts and scales to multiple distributed workers.

\`\`\`toml
# aura.toml
[jobs]
backend = "saq"
broker_url = "redis://localhost:6379/0"
\`\`\`

---

## 5.3 Writing Background Tasks & Periodic Cron Jobs
Tasks are declared using the \`@task\` or \`@periodic\` decorators.

\`\`\`python
# modules/users/tasks.py
from aura.jobs.decorators import task, periodic
from modules.users.services import EmailService
from aura import inject
from typing import Annotated

# Standard background task with retries and timeout constraints
@task(queue="emails", retry=3, timeout=60)
async def send_welcome_email(user_id: int, email: str, mailer: EmailService):
    """Asynchronously dispatches welcome emails to new users."""
    # Dependency injection resolves 'mailer' automatically within the task scope!
    await mailer.send_user_welcome(user_id, email)

# Periodic cron-based job
@periodic(cron="0 2 * * *", run_on_startup=False)
async def database_cleanup():
    """Runs daily database cleanup routines at 2:00 AM."""
    # Automated database cleanups run here
    pass
\`\`\`

### `@task` Parameters:
- **\`queue\`**: The target queue name (defaults to \`"default"\`).
- **\`retry\`**: How many times to retry the task if it fails.
- **\`timeout\`**: Max execution time in seconds.
- **\`priority\`**: Higher numbers denote higher priority.

---

## 5.4 Dispatching Tasks & Getting Results
You can trigger tasks from anywhere in your codebase (like a service or controller) using the \`.dispatch()\` method:

\`\`\`python
# 1. Fire-and-forget dispatch (non-blocking)
await send_welcome_email.dispatch(user_id=42, email="user@aura.dev")

# 2. Delayed dispatch (runs after 10 minutes)
await send_welcome_email.dispatch(
    user_id=42, 
    email="user@aura.dev", 
    delay=600  # seconds
)

# 3. Executing a task and waiting for the result (useful for testing)
job = await send_welcome_email.dispatch(user_id=42, email="user@aura.dev")
result = await send_welcome_email.wait_for_result(job.task_id, timeout=10)
print(result.status)  # "SUCCESS"
\`\`\`

---

## 5.5 Dependency Injection inside Workers
Aura background workers manage dependency lifecycles just like HTTP requests:

1. When a task starts, the worker allocates an isolated container **Scope**.
2. Constructor parameters in task definitions are resolved automatically.
3. Once execution completes, the worker releases the scope and clean up scoped resources (like database connections).

---

## 5.6 Robustness: Exponential Backoff & Dead Letter Queues
1. **Exponential Backoff:** If a task with retries fails due to a network glitch, Aura delays retrying using exponential backoff:
   - 1st failure: retries after 10 seconds.
   - 2nd failure: retries after 40 seconds.
   - 3rd failure: retries after 160 seconds.
2. **Dead Letter Queue (DLQ):** If a task exhausts all retry attempts, Aura moves it to a Dead Letter Queue (\`DLQ\`) and records the traceback error. This prevents failing tasks from blocking active queues, allowing you to debug them later.

---

## 5.7 CLI Worker Management
Start your workers using the Aura CLI:

\`\`\`bash
# Start a worker processing all queues
aura worker

# Process only specific queues
aura worker --queue emails --queue critical

# Set custom worker concurrency
aura worker --concurrency 8

# Enable auto-reload (useful for development)
aura worker --reload
\`\`\`
`
    },
    {
      id: "templates-routing",
      title: "6. HTML Templates, Starlette Routing & Islands Architecture",
      summary: "Guide to Starlette asynchronous routing, type-safe TemplateContext, component rendering, Islands Architecture, and real-time streaming with SSE.",
      markdown: `# Templates, HTML Routing & Islands Architecture

## 6.1 Async Routing & ASGI Streaming
Aura features a highly optimized asynchronous HTML routing and streaming engine. By using \`@html\` instead of JSON-focused endpoint decorators, you define routes optimized for fast server-side HTML rendering.

```
HTTP GET Request ---> Controller Handler ---> TemplateContext Validation
                                                        |
Jinja2 Asynchronous Stream <--- render() <--- Jinja2 Compilation
```

---

## 6.2 Type-Safe HTML Rendering with `TemplateContext`
In traditional MVC frameworks like Django, template context is a plain dictionary, which makes it easy to introduce typos or pass incorrect types.

Aura solves this using a type-safe **TemplateContext** backed by **Pydantic v2**:

\`\`\`python
# modules/users/schemas.py
from aura.templates import TemplateContext
from .schemas import UserResponse

class UserListContext(TemplateContext):
    title: str
    users: list[UserResponse]
    total_count: int
    current_page: int = 1
    
    @property
    def total_pages(self) -> int:
        return (self.total_count + 19) // 20
\`\`\`

Render the context inside your controller:

\`\`\`python
# modules/users/controller.py
from aura.templates import html, render, HtmlResponse
from .service import UserService
from .schemas import UserListContext

class UserController:
    def __init__(self, service: UserService):
        self.service = service

    @html("/list")
    async def view_users(self) -> HtmlResponse:
        users = await self.service.list_active_users()
        # Returns a validated, type-safe HTML response
        return await render(
            "users/list.html",
            UserListContext(
                title="Active Users Directory",
                users=users,
                total_count=len(users)
            )
        )
\`\`\`

The template template file (\`templates/users/list.html\`):
\`\`\`html
{% extends "base.html" %}

{% block content %}
<h1 class="text-2xl font-bold">{{ title }}</h1>
<span class="text-sm">Total users: {{ total_count }}</span>

<ul class="mt-4 space-y-2">
  {% for user in users %}
    <li class="p-3 border rounded">{{ user.name }} ({{ user.email }})</li>
  {% endfor %}
</ul>
{% endblock %}
\`\`\`

---

## 6.3 Reusable HTML Components with Type-Safe `Props`
Aura introduces reusable HTML **Components** with type-safe props:

\`\`\`python
# components/user_card.py
from aura.templates import Component, TemplateContext
from modules.users.schemas import UserResponse

class UserCardProps(TemplateContext):
    user: UserResponse
    show_details: bool = False
    badge_color: str = "indigo"

class UserCardComponent(Component):
    template = "components/user_card.html"
    Props = UserCardProps
    name = "user_card"  # The identifier name registered in the Jinja2 context
\`\`\`

Render the component inside any Jinja2 template:
\`\`\`html
{# Render our reusable component passing type-safe props #}
{{ component("user_card", user=user, show_details=True, badge_color="green") }}
\`\`\`

---

## 6.4 Preventing N+1 Database Pitfalls in Templates
A common database performance issue occurs when templates lazy-load relationships while looping over records (e.g., accessing \`post.author.name\` when the author wasn't eagerly loaded).

Aura actively prevents this by encouraging you to resolve relationship data inside your Python code (using DTOs/TemplateContexts) rather than letting templates load database relations lazily.

\`\`\`python
# ✅ THE SECURE AND CORRECT APPROACH (Explicit DTOs)
class PostItemDTO(TemplateContext):
    title: str
    author_name: str  # Plain string, not a lazy-loaded ORM relationship!
    comment_count: int

class PostListContext(TemplateContext):
    posts: list[PostItemDTO]
\`\`\`

---

## 6.5 Modern Client-Side Hydration: Islands Architecture
For pages that are mostly static but require complex interactive widgets (like a live chart or interactive form), Aura supports **Islands Architecture**:

\`\`\`python
# Pass interactive widget props dynamically to the layout
class DashboardContext(TemplateContext):
    total_sales: float
    # Props that will be serialized to JSON and hydrated by client-side JS
    chart_island_props: dict 
\`\`\`

In your HTML template:
\`\`\`html
{# Static HTML content is rendered instantly on the server #}
<div class="stat-card">
  <span>Total Revenue: {{ total_sales | currency }}</span>
</div>

{# Interactive JS Island hydrated on-demand by client-side JS #}
<div data-island="LiveSalesChart" 
     data-props="{{ chart_island_props | tojson }}">
</div>

<script src="/static/js/island-hydrator.js"></script>
\`\`\`

---

## 6.6 Real-Time Asynchronous Streams with `@sse`
For real-time updates without the overhead of WebSockets, Aura supports **Server-Sent Events (SSE)** via the \`@sse\` decorator:

\`\`\`python
# modules/events/controller.py
from aura.templates import sse
from aura.core.request import AuraRequest
import asyncio

class NotificationController:
    @sse("/notifications/stream")
    async def stream_notifications(self, request: AuraRequest):
        """Asynchronously streams notifications to clients as they arrive."""
        while True:
            # Yield events as JSON payloads
            yield {
                "event": "new_notification",
                "data": {
                    "message": "A new task has been registered",
                    "time": "Just now"
                }
            }
            await asyncio.sleep(2.0)
\`\`\`

---

## 6.7 Testing HTML & HTMX Routes
Aura provides a built-in testing client (\`TestClient\`) to test templates, endpoints, and HTMX headers:

\`\`\`python
from aura.testing import TestClient
from main import app

client = TestClient(app)

def test_user_list_page():
    # Test standard HTML rendering
    res = client.get("/users/list")
    assert res.status_code == 200
    assert "Active Users Directory" in res.text

def test_htmx_partial_rendering():
    # Simulates an HTMX request
    res = client.get("/users/list", headers={"HX-Request": "true"})
    assert res.status_code == 200
    # Returns only the partial list instead of the full HTML page layout
    assert "<html" not in res.text
    assert "<ul class=\"mt-4" in res.text
\`\`\`
`
    }
  ]
};

# 🗄️ Database Seeding

O Aura fornece um sistema robusto, elegante e totalmente assíncrono para popular o banco de dados da sua aplicação com dados iniciais ou de teste. A infraestrutura de seeders do Aura é construída com foco em **Developer Experience (DX)**, integrando-se nativamente com o container de Injeção de Dependências (DI) e oferecendo proteção para ambientes de produção.

---

## 🌟 Principais Recursos

- 💉 **Suporte a Injeção de Dependências (DI)**: Todos os seeders são anotados nativamente com `@injectable`, permitindo injetar repositórios, serviços externos ou qualquer outra dependência no construtor.
- 🔗 **Resolução Recursiva (Chaining)**: Execute múltiplos seeders em ordem de forma hierárquica usando `await self.call([SubSeederClass])`.
- 💾 **Persistência Transparente**: Método `await self.save(obj)` integrado à `ContextVar` local do ciclo de vida assíncrono com transações automáticas e fallbacks seguros.
- 🛡️ **Controle de Idempotência**: Evite duplicação de dados com rastreamento integrado através da tabela de metadados `_aura_seeded` e flag `--once`.
- 🚨 **Proteção de Produção**: Bloqueio visual dinâmico com confirmação obrigatória para evitar execução acidental de seeders em banco de dados de produção.

---

## 🏗️ A Classe Base `Seeder`

Todo seeder no Aura herda da classe base `Seeder` (`aura.orm.seeders.Seeder`), que já vem anotada com o decorador `@injectable` nativo do framework. Isso significa que você pode receber qualquer dependência no seu construtor (`__init__`), e o Aura fará a resolução automática antes de executar o método `run`.

### Métodos Principais da API:

1. **`async def run(self) -> None`**
   O método principal que você deve sobrescrever contendo a lógica de população de dados do seeder.

2. **`async def save(self, obj: Any) -> None`**
   Salva uma instância de modelo de forma inteligente. Ele verifica automaticamente se há uma sessão de transação ativa no contexto assíncrono local (`current_session`).
   - Se houver uma sessão ativa, o Aura adiciona o objeto à sessão (`session.add(obj)`) e executa um `flush` para gerar IDs e chaves primárias sem commitar prematuramente. A transação inteira será commitada atomicamente ao final do seeder.
   - Se não houver uma sessão no contexto (ex: se executado fora da CLI do seeder), ele cria uma nova transação isolada com `async with db.session() as session:`, adiciona e realiza o commit automático ao final do bloco.

3. **`async def call(self, seeders: list[type[Seeder]]) -> None`**
   Recebe uma lista de classes que herdam de `Seeder`. O Aura resolve cada uma delas dinamicamente via container de DI, garantindo o ciclo de vida correto das dependências, e as executa em lote na ordem especificada.

---

## 💻 Exemplo Prático Completo

Abaixo está um cenário completo demonstrando como criar um seeder individual utilizando injeção de dependências e um seeder principal (`DatabaseSeeder`) que orquestra a execução em cadeia.

### 1. Definindo o Modelo e o Repositório

```python
# modules/users/models.py
from aura.orm import AuraModel, CharField, EmailField
from sqlalchemy.orm import Mapped

class User(AuraModel):
    __tablename__ = "users"

    name: Mapped[str] = CharField(max_length=100)
    email: Mapped[str] = EmailField(unique=True)
```

```python
# modules/users/repository.py
from aura.orm import Repository
from .models import User

class UserRepository(Repository[User]):
    model = User
```

### 2. Criando Seeders com Injeção de Dependência

Graças ao suporte nativo de DI, o seeder pode injetar o `UserRepository` diretamente no construtor para realizar as operações de persistência ou lógica de negócios:

```python
# database/seeders/user_seeder.py
from aura.orm import Seeder
from modules.users.repository import UserRepository
from modules.users.models import User

class UserSeeder(Seeder):
    def __init__(self, user_repo: UserRepository) -> None:
        self.user_repo = user_repo

    async def run(self) -> None:
        # Dados para semear
        users_data = [
            {"name": "Alice Silva", "email": "alice@aura.dev"},
            {"name": "Bob Souza", "email": "bob@aura.dev"},
            {"name": "Charlie Santos", "email": "charlie@aura.dev"},
        ]

        for u_data in users_data:
            # Verifica se o usuário já existe
            exists = await self.user_repo.exists(email=u_data["email"])
            if not exists:
                user = User(name=u_data["name"], email=u_data["email"])
                # Salva usando a sessão transacional ativa
                await self.save(user)
```

### 3. Criando o Seeder Principal (`DatabaseSeeder`)

Por padrão, a CLI do Aura busca por uma classe chamada `DatabaseSeeder` para executar as sementes da aplicação. Você pode usá-la para orquestrar e chamar outros seeders na ordem lógica necessária (ex: criar Roles antes de Users, e Users antes de Posts):

```python
# database/seeders/main_seeder.py
from aura.orm import Seeder
from .user_seeder import UserSeeder

class DatabaseSeeder(Seeder):
    async def run(self) -> None:
        # Resolução assíncrona recursiva de sub-seeders
        await self.call([
            UserSeeder,
            # Outros sub-seeders adicionados aqui
        ])
```

---

## 🎛️ Comandos de Linha de Comando (CLI)

O Aura expõe comandos poderosos sob o namespace `aura db seed` para controlar a execução dos seus seeders.

### 1. Executando o Seeder Principal
Por padrão, o comando executa a classe `DatabaseSeeder`:
```bash
aura db seed
```

### 2. Executando um Seeder Específico
Se você deseja rodar apenas um seeder isolado, utilize a flag `--class` ou `-c`:
```bash
aura db seed --class UserSeeder
```

### 3. Evitando Execuções Duplicadas (Idempotência)
Para rodar seeders de forma idempotente, use a flag `--once`. O Aura verificará na tabela `_aura_seeded` se este seeder específico já foi executado alguma vez. Se sim, ele será ignorado automaticamente.
```bash
aura db seed --once
```

> [!NOTE]
> O Aura cria automaticamente a tabela `_aura_seeded` no banco de dados se ela não existir para armazenar a lista histórica de classes executadas com `--once`.

---

## 🛡️ Segurança e Proteção em Produção

Rodar seeders de teste em ambientes de produção pode corromper ou sobrescrever dados cruciais. O Aura possui uma barreira de proteção visual e lógica integrada no core.

Se o Aura detectar que a aplicação está executando em um ambiente de produção — seja pela variável de ambiente `AURA_ENV=production`/`ENV=production` ou pela presença de strings como `prod` ou `production` na URL do banco de dados (`AURA__DATABASE__URL`) —, o terminal exibirá um painel de alerta de alto contraste e exigirá confirmação humana obrigatória para prosseguir:

```text
┌─────────────────────────────── Production Alert ───────────────────────────────┐
│ WARNING: You are running in a PRODUCTION environment!                          │
└────────────────────────────────────────────────────────────────────────────────┘
Are you sure you want to run the database seeders? [y/N]: 
```

Se o operador escolher `N` ou pressionar Enter sem selecionar `y`, o processo será abortado imediatamente com código de saída de erro, garantindo total integridade e segurança à infraestrutura.

---

## 💡 Melhores Práticas de Seeding

> [!TIP]
> **Use sempre `self.save()` ao invés de commits manuais:** Evite chamar `await session.commit()` diretamente dentro do método `run()` do seu seeder. A CLI do Aura gerencia a transação inteira de forma atômica no escopo do container assíncrono. Chamar commit manualmente impede rollback automático em caso de erro nos seeders posteriores.

> [!TIP]
> **Combine seeders com fábricas (factories) e utilize Sobreposição Parcial:**
> Para gerar dados fictícios volumosos ou registros iniciais específicos em seu seeder, use as fábricas do Aura. Quando você passa argumentos nomeados (ex: `await UserFactory().create(name="Alice")`), o Aura realiza a **sobreposição parcial**, alterando **apenas** os atributos especificados. Todos os demais campos não fornecidos são populados automaticamente através das definições padrão da fábrica (como expressões lambda e callables do `Faker`).
>
> Veja um exemplo prático de um seeder usando factories:
>
> ```python
> # database/seeders/user_factory_seeder.py
> from aura.orm import Seeder
> from database.factories import UserFactory
> 
> class UserFactorySeeder(Seeder):
>     async def run(self) -> None:
>         # Cria a "Alice" sobrepondo apenas o nome; o email é gerado automaticamente pelo Faker
>         alice = await UserFactory().create(name="Alice")
>         
>         # Cria o "Bob" sobrepondo apenas o email; o nome é gerado automaticamente pelo Faker
>         bob = await UserFactory().create(email="bob@example.com")
>         
>         # Cria mais 10 usuários com dados totalmente aleatórios e automáticos
>         await UserFactory().create_many(10)
> ```

---

Com esse sistema integrado, semear bancos de dados de teste ou carregar registros mestres de sistema torna-se um fluxo limpo, modular, testável e extremamente intuitivo.

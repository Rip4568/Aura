# Shell Interativo REPL — Aura Tinker

## Visão Geral e DX (Developer Experience)

O desenvolvimento de aplicações web modernas frequentemente exige testar consultas de banco de dados, interagir com serviços de negócio e validar schemas DTO de forma rápida e iterativa. Tradicionalmente, fazer isso no Python REPL padrão exige importar manualmente dezenas de módulos, instanciar manualmente o banco de dados, inicializar o container de injeção de dependências e gerenciar loops de eventos assíncronos. Essa fricção prejudica drasticamente a experiência do desenvolvedor (DX).

O **Aura Tinker** (`aura tinker`) é um shell interativo assíncrono projetado especificamente para eliminar essa barreira. Em menos de um segundo, ele:

- Inicializa o banco de dados e conecta ao pool de conexões de forma assíncrona.
- Executa o auto-discovery (descoberta automática) de todos os componentes do projeto.
- Inicializa o container de Injeção de Dependências (DI) em segundo plano.
- Importa todos os Models, Repositories, Services e Schemas automaticamente no namespace global.
- Configura o suporte a loops assíncronos (`top-level await` ou helper síncrono) facilitando a execução de funções `async def`.

```
$ aura tinker

     _      _   _   ____        _
    / \    | | | | |  _ \      / \
   / _ \   | | | | | |_) |    / _ \
  / ___ \  | |_| | |  _ <    / ___ \
 /_/   \_\  \___/  |_| \_\  /_/   \_\  t i n k e r

----------------------------------------------------------------------
App: Blog API | REPL Shell: IPYTHON
✓ Database 'db' initialized and connected.
----------------------------------------------------------------------
Models: Post, User, Comment
Repositories: PostRepository, UserRepository, CommentRepository
Services: PostService, UserService, CommentService
Schemas: CreatePostDTO, PostResponse, CreateUserDTO, UserResponse
----------------------------------------------------------------------
Async Tip: IPython supports top-level await! Run: await db.session.execute(...)
----------------------------------------------------------------------

In [1]:
```

---

## Como Iniciar

Para inicializar o shell REPL do Aura, execute o comando `aura tinker` na raiz do seu projeto. O Aura aceita opções que permitem customizar o comportamento do shell e o backend utilizado.

```bash
aura tinker [OPTIONS]
```

### Opções Disponíveis

- **`--repl <ipython|bpython|python>`**: Define o interpretador REPL de backend.
  - `ipython` (Padrão): Suporta coloração de sintaxe avançada, auto-completar dinâmico e **top-level await nativo**.
  - `bpython`: Interface de terminal rica com auto-completar in-line e dicas de parâmetros de funções.
  - `python`: REPL padrão do Python. Usado como fallback automático caso as bibliotecas `ipython` ou `bpython` não estejam instaladas.
- **`--no-db`**: Inicializa o shell pulando a inicialização automática do banco de dados (`db`). Ideal para testar utilitários que não dependem do banco de dados, ou em ambientes sem conexão configurada.

---

## O Mecanismo de Auto-Discovery

O grande benefício de DX do `aura tinker` é o seu poderoso carregador recursivo. O shell varre dinamicamente a estrutura de arquivos da raiz do projeto (`CWD`) e importa de forma inteligente as classes encontradas, categorizando-as em quatro frentes no escopo global do interpretador:

1. **Models**: Qualquer classe herdada de `AuraModel` (ex: `Post`, `User`).
2. **Repositories**: Qualquer classe baseada em `Repository` (ex: `PostRepository`).
3. **Schemas**: Qualquer classe herdada de `Schema` ou DTO (ex: `CreatePostDTO`, `PostResponse`).
4. **Services**: Qualquer classe que atenda a pelo menos um dos seguintes critérios:
   - Decorada com `@injectable` (contendo o atributo interno `__aura_injectable__`).
   - Cujo nome termine com `"Service"` (ex: `UserService`).
   - Declarada dentro de arquivos com nome `service.py` ou `services.py`.

> [!NOTE]
> Para evitar travamentos e poluição do namespace, o auto-discovery ignora recursivamente as seguintes pastas do projeto:
> ` .git `, ` .venv `, ` venv `, ` tests `, ` migrations `, ` __pycache__ `, ` storage `, ` dist ` e ` build `.

---

## Funcionamento Assíncrono e Top-Level Await

A maioria das operações do Aura é assíncrona (`async def`). Lidar com isso no REPL tradicional normalmente requer o gerenciamento explícito do loop de eventos do `asyncio`. No Aura Tinker, a execução assíncrona é facilitada dependendo do REPL selecionado:

### 1. IPython (Top-Level Await Nativo)
Se você estiver utilizando o backend `ipython` (o padrão), o Aura configura o interpretador com `autoawait = True` e integra o loop de eventos ao loop do IPython. Isso permite que você digite `await` diretamente no terminal:

```python
# Consulta direta e assíncrona no shell do IPython
posts = await PostRepository(db.session).list()
```

### 2. Outros Backends (Helper `sync(...)`)
No caso de fallback para o `bpython` ou `python` padrão (que não possuem suporte nativo a `top-level await`), o Aura injeta automaticamente um helper global chamado `sync(...)`. Sob o capô, este utilitário usa a biblioteca `nest-asyncio` para rodar coroutines de forma síncrona sem conflitos de loop:

```python
# Execução síncrona de uma coroutine usando o helper sync
posts = sync(PostRepository(db.session).list())
```

---

## Exemplos Práticos de Uso

Abaixo estão alguns exemplos cotidianos de como usar o `aura tinker` para aumentar sua produtividade.

### 1. Consultas Rápidas no Banco com AuraQL (`Q`)

O Aura injeta o construtor AuraQL (`Q`) no namespace global do shell, tornando a montagem de queries expressiva e rápida:

```python
# IPython: Top-Level Await
query = Q(Post).where(published=True).order_by("-created_at")
posts = await PostRepository(db.session).list(query)

# bpython/python REPL: usando o helper sync
query = Q(Post).where(published=True)
posts = sync(PostRepository(db.session).list(query))
```

### 2. Resolvendo Dependências com o Container de DI

O Aura Tinker busca a instância da aplicação `app` definida no seu `main.py` e extrai o container global de Injeção de Dependências, expondo-o no namespace como `container`.
O container é inicializado/aquecido automaticamente (`container.startup()`) no momento em que o shell é aberto. Isso permite resolver serviços de forma transparente:

```python
# Resolvendo o UserService do container
user_service = await container.get(UserService)

# Usando o serviço recuperado
user = await user_service.get_user(1)
print(user.name)
```

> [!TIP]
> Caso queira instanciar repositórios ou serviços manualmente no shell sem usar o container global de DI, basta passar a sessão ativa do banco de dados: `repo = PostRepository(db.session)`.

### 3. Escrevendo e testando Logs estruturados

A facade `Log` do **AuraLogSystem** é importada automaticamente no namespace como `Log`. Isso ajuda a testar regras de formatação, sanitização e saída de logs no próprio REPL:

```python
# Registra um log de informação
Log.info("Teste de auditoria via REPL", usuario="Tinker Shell")

# Testa a sanitização automática de dados confidenciais
Log.warning("Atualização de dados sensíveis", payload={"password": "minhasenhasupersecreta"})
# Saída no terminal/arquivo virá devidamente higienizada:
# [WARNING] Atualização de dados sensíveis | payload: {'password': '***REDACTED***'}
```

### 4. Testando Schemas e Validação de DTOs

Importe e teste a validação de dados usando os DTOs do projeto instantaneamente:

```python
from pydantic import ValidationError

try:
    # Tenta instanciar o schema com dados inválidos
    dto = CreateUserDTO(email="invalid-email")
except ValidationError as e:
    print(e.errors())
```

### 5. Gerenciamento de Sessão de Banco de Dados (Transações)

Ao interagir com o banco de dados via REPL, existem duas abordagens principais para gerenciar as sessões do SQLAlchemy, dependendo das suas necessidades de velocidade e segurança:

#### Opção 1 (Padrão Recomendado): Gerenciador de Contexto `async with db.session()`
Esta é a abordagem padrão utilizada em produção e recomendada para testes complexos. Ela garante que a transação seja gerenciada de forma totalmente segura (com commit automático ao final ou rollback em caso de falhas) e fecha a sessão automaticamente liberando os recursos:

```python
# IPython com top-level await
async with db.session() as session:
    repo = PostRepository(session)
    new_post = await repo.create(title="Nova Postagem", body="Conteúdo do post")
    # O commit automático e fechamento seguro ocorrem aqui ao sair do bloco
```

#### Opção 2 (Testes rápidos no REPL): Fábrica de Sessões Direta `db._session_factory()`
Escrever blocos indentados (`async with`) no terminal pode ser desconfortável ou lento durante sessões de depuração rápida. Para contornar isso e digitar código linear sem indentação, você pode instanciar uma sessão isolada diretamente a partir da factory do banco de dados:

```python
# IPython com top-level await (Sem indentação)
session = db._session_factory()
repo = PostRepository(session)

# Executa operações normais lineares
new_post = await repo.create(title="Post Linear no REPL", body="Perfeito para testes rápidos")

# IMPORTANTE: Você é responsável por gerenciar a transação manualmente!
await session.commit()  # Salva as alterações de forma explícita
await session.close()   # Fecha a sessão manualmente para liberar a conexão no pool
```

> [!WARNING]
> Ao utilizar a Opção 2 (`db._session_factory()`), certifique-se de chamar `await session.close()` ao finalizar. Caso contrário, a conexão pode permanecer aberta no pool de forma indefinida, gerando vazamento de recursos.


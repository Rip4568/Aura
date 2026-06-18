# Aura Tinker

`aura tinker` abre um shell REPL interativo com auto-discovery de models, repositories, services e schemas do projeto.

## Uso básico

```bash
# IPython (padrão, com top-level await)
aura tinker

# REPL Python padrão
aura tinker --repl python

# bpython (se instalado)
aura tinker --repl bpython

# Sem conectar ao banco
aura tinker --no-db
```

## O que é carregado automaticamente

O comando percorre o diretório atual (excluindo `.git`, `venv`, `tests`, `migrations`, etc.) e importa:

| Categoria | Critério de descoberta |
|-----------|------------------------|
| Models | subclasses de `AuraModel` |
| Repositories | subclasses de `Repository` |
| Services | classes com `@injectable` |
| Schemas | subclasses de `BaseModel` (Pydantic) |

Objetos descobertos ficam disponíveis no namespace do REPL pelo nome da classe.

## App e container

Se um arquivo `main.py` (ou similar) exporta uma instância `Aura`, o tinker injeta:

- `app` — instância da aplicação
- `container` — `DIContainer` da app (com `startup()` já executado)

## Banco de dados

Por padrão, o tinker inicializa o singleton global `db` a partir de `AURA__DATABASE__URL` (ou config do projeto). Use `--no-db` para pular essa etapa.

## Exemplos

```python
# Listar models descobertos
>>> list(models.keys())

# Query rápida (com db conectado)
>>> await User.objects.using(session).all()

# Resolver serviço via DI
>>> svc = await container.resolve(UserService)
```

## Requisitos opcionais

| Extra | Uso |
|-------|-----|
| `ipython` | REPL padrão com syntax highlighting e top-level await |
| `bpython` | REPL alternativo (`--repl bpython`) |
| `nest_asyncio` | Helper `sync()` para coroutines no REPL Python puro |

## Implementação

Código-fonte: `aura/cli/commands/tinker.py`  
Testes: `tests/test_tinker.py`

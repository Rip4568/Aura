# Contributing to Aura Framework

Thank you for your interest in contributing to Aura! This document describes the process and guidelines for contributing.

## Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/jonathasdavidd/Aura.git
cd Aura
```

2. **Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

3. **Install in development mode with all optional extras**

```bash
pip install -e ".[dev,sqlalchemy,jwt,session,templates,saq]" aiosqlite
```

4. **Run tests**

```bash
python -m pytest tests/ -q --tb=short
```

5. **Run linting and type checks**

```bash
python -m ruff check aura/ tests/
python -m mypy aura/ --ignore-missing-imports
python -m mypy tests/ --ignore-missing-imports
```

> **Nota (wave 7):** `mypy` em `aura/` e `tests/` está completo — **0 erros** em ambos. Consulte `docs/pending.md` para o estado do roadmap.

6. **Pre-commit hooks (recomendado)**

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files   # validação manual antes do push
```

Hooks configurados em `.pre-commit-config.yaml`: **ruff** (com `--fix` em `aura/` e `tests/`) e **mypy** em `aura/` + `tests/` (always_run).

## Code Style

- Use **ruff** for linting (line length: 100)
- Use **mypy** with strict mode for type checking (`aura/` e `tests/` — 0 erros)
- All public APIs must have **type hints** and **docstrings** in English
- Follow PEP 8 and PEP 526 conventions

## Pull Request Process

1. Fork the repository and create a feature branch from `main`
2. Read `docs/pending.md` before starting — evite duplicar trabalho em andamento
3. Write tests for new functionality
4. Ensure all tests pass and type checks succeed for `aura/` and `tests/`
5. Update documentation if you change public API or breaking behavior (see `docs/decisions/`)
6. Submit a pull request with a clear description

## Breaking Changes

Mudanças breaking exigem:

- Entrada em `docs/decisions/ADR-*.md`
- Nota em `docs/pending.md` e README (seção limitações ou segurança)
- Testes de migração/contrato

Exemplos recentes (v1.2.x–v1.4.0): `QuerySet.delete(allow_unfiltered=True)`, extra `[jwt]` com PyJWT, `JWTGuard(require_exp=True)` padrão, formato 422 estruturado, cookie de sessão só quando mutado.

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(di): add scoped lifetime support
fix(routing): return 422 on invalid param coercion
fix(orm): require allow_unfiltered for unfiltered delete
docs(schema): clarify Schema vs ResponseSchema usage
test(guards): add integration tests for JWTGuard with PyJWT
```

## Architecture Guidelines

- **Async-first**: prefer `async def` for I/O bound operations
- **Type-safe**: use Pydantic v2 for data validation
- **Modular**: keep modules decoupled and independently testable
- **No circular imports**: use `TYPE_CHECKING` guards when needed
- **SDD**: the spec defines the contract, implementation follows
- **Verify before marking done**: `grep` + `pytest` no módulo alterado

## Reporting Issues

Please include:
- Python version and OS
- Aura version (`aura version` or `pyproject.toml`)
- Minimal reproducible example
- Full traceback

## Code of Conduct

Be respectful, constructive, and inclusive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

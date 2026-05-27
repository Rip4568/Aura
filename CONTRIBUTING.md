# Contributing to Aura Framework

Thank you for your interest in contributing to Aura! This document describes the process and guidelines for contributing.

## Development Setup

1. **Clone the repository**

```bash
git clone https://github.com/your-org/aura-framework.git
cd aura-framework
```

2. **Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
```

3. **Install in development mode with dev dependencies**

```bash
pip install -e ".[dev]"
```

4. **Run tests**

```bash
pytest tests/ -v
```

5. **Run linting and type checks**

```bash
ruff check aura/
mypy aura/
```

## Code Style

- Use **ruff** for linting (line length: 100)
- Use **mypy** with strict mode for type checking
- All public APIs must have **type hints** and **docstrings** in English
- Follow PEP 8 and PEP 526 conventions

## Pull Request Process

1. Fork the repository and create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass and type checks succeed
4. Update documentation if needed
5. Submit a pull request with a clear description

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(di): add scoped lifetime support
fix(routing): handle missing path parameters correctly
docs(schema): clarify Schema vs ResponseSchema usage
test(guards): add integration tests for JWTGuard
```

## Architecture Guidelines

- **Async-first**: prefer `async def` for I/O bound operations
- **Type-safe**: use Pydantic v2 for data validation
- **Modular**: keep modules decoupled and independently testable
- **No circular imports**: use `TYPE_CHECKING` guards when needed
- **SDD**: the spec defines the contract, implementation follows

## Reporting Issues

Please include:
- Python version and OS
- Aura version
- Minimal reproducible example
- Full traceback

## Code of Conduct

Be respectful, constructive, and inclusive. We follow the [Contributor Covenant](https://www.contributor-covenant.org/).

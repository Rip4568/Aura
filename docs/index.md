# Aura Framework

Aura is an async-first, type-safe Python web framework inspired by NestJS. It combines structured modules, real dependency injection, and Spec-Driven Development on top of Starlette and Pydantic v2.

## Quick start

```bash
pip install aura-web
aura new my-project
cd my-project
aura run
```

## Documentation map

| Topic | Location |
|-------|----------|
| Roadmap & backlog | [pending.md](pending.md) |
| Architecture decisions | [decisions/](decisions/) |
| Interactive shell (`aura tinker`) | [tinker.md](tinker.md) |
| Changelog | [../CHANGELOG.md](../CHANGELOG.md) |

## Quality bar

Every release is validated with:

- `pytest` across Python 3.10–3.13
- `mypy` on `aura/` and `tests/`
- `ruff` lint
- Minimum 75% code coverage on `aura/`

.PHONY: test typecheck lint check install

# Prefer `python` (Windows-friendly); override with `make PYTHON=python3` on Unix if needed.
PYTHON ?= python

install:
	$(PYTHON) -m pip install -e ".[dev,sqlalchemy,jwt,session,templates,uvicorn]" aiosqlite

test:
	$(PYTHON) -m pytest tests/ -q

typecheck:
	$(PYTHON) -m mypy aura/ --ignore-missing-imports
	$(PYTHON) -m mypy tests/ --ignore-missing-imports

lint:
	$(PYTHON) -m ruff check aura/ tests/

check: typecheck lint test

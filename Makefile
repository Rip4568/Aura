.PHONY: test typecheck lint check install

install:
	pip install -e ".[dev]"

test:
	python3 -m pytest tests/ -x -q

typecheck:
	python3 -m mypy aura/ --ignore-missing-imports

lint:
	python3 -m ruff check aura/ tests/

check: typecheck lint test

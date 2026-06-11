VENV     := .venv
BIN      := $(VENV)/bin
ACTIVATE := . $(BIN)/activate &&

PYTHON_PKGS        := pybsen
FORMAT_CHECK_PATHS := $(PYTHON_PKGS) tests

PYTEST := pytest -v

.PHONY: all static lint typecheck test reformat install-hooks clean

all: static

static: lint typecheck test

lint: $(VENV)
	$(ACTIVATE) ruff check $(FORMAT_CHECK_PATHS)
	$(ACTIVATE) ruff format --check $(FORMAT_CHECK_PATHS)

typecheck: $(VENV)
	$(ACTIVATE) mypy $(PYTHON_PKGS)

test: $(VENV)
	$(ACTIVATE) $(PYTEST) tests/

reformat: $(VENV)
	$(ACTIVATE) ruff check --fix $(FORMAT_CHECK_PATHS)
	$(ACTIVATE) ruff format $(FORMAT_CHECK_PATHS)

$(VENV): pyproject.toml
	python3 -m venv $(VENV)
	$(ACTIVATE) pip install -e ".[dev]"
	touch $(VENV)

install-hooks: $(VENV)
	$(ACTIVATE) pre-commit install

clean:
	rm -rf $(VENV) __pycache__ .mypy_cache .pytest_cache

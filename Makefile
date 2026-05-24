# ivycode — common developer commands.
# Run `make help` to see the full list.

PYTHON ?= python
PKG    := ivycode

.PHONY: help install format format-check lint type test check doctor index clean

help:  ## Show this help.
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
		/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

install:  ## Install the project in editable mode with dev extras.
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

format:  ## Auto-format the codebase with ruff.
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

format-check:  ## Verify formatting without changing files.
	$(PYTHON) -m ruff format --check .

lint:  ## Run ruff lint.
	$(PYTHON) -m ruff check .

type:  ## Run mypy in strict mode.
	$(PYTHON) -m mypy $(PKG)

test:  ## Run the test suite.
	$(PYTHON) -m pytest

doctor:  ## Run `ivycode doctor`.
	$(PYTHON) -m $(PKG) doctor

index:  ## Re-index the current project into CodeGraph.
	$(PYTHON) -m $(PKG) index --force

check: format-check lint type test doctor  ## Full pre-PR validation.

clean:  ## Remove caches and build artefacts.
	rm -rf .mypy_cache .pytest_cache .ruff_cache build dist *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

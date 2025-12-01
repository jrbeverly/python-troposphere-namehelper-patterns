# Developer loop for the `namehelper` library.
#
# The baseline loop (test / e2e / check) uses only the Python standard library
# so it works with zero installs. `make setup` provisions optional tooling into
# a repo-local package directory so it still works in PEP 668 environments.

# Run tests and examples against the src/ tree without requiring an install.
export PYTHONPATH := .python_packages:src$(if $(PYTHONPATH),:$(PYTHONPATH))

PYTHON ?= python3
SETUP_GROUPS ?= dev examples

.DEFAULT_GOAL := help
.PHONY: help setup test e2e check clean

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Install optional tooling into repo-local .python_packages
	$(PYTHON) tools/install_optional_deps.py $(SETUP_GROUPS)

test: ## Run unit tests (stdlib unittest, zero dependencies)
	$(PYTHON) -m unittest discover -s tests/unit -p 'test_*.py' -t . -v

e2e: ## Run integration + contract verification layers
	$(PYTHON) -m unittest discover -s tests/integration -p 'test_*.py' -t . -v
	$(PYTHON) -m unittest discover -s tests/contract -p 'test_*.py' -t . -v

check: ## Local static check (byte-compile all sources)
	$(PYTHON) -m compileall -q src tests examples

clean: ## Remove build/cache artifacts
	rm -rf build dist src/*.egg-info .pytest_cache .python_packages
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

.PHONY: install test coverage lint format clean help

PYTHON := python3
PIP    := pip3
SRC    := src
TESTS  := tests

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install all dependencies
	$(PIP) install -e ".[dev]"

install-prod:  ## Install production dependencies only
	$(PIP) install -e .

test:  ## Run test suite
	pytest $(TESTS)/ -v

coverage:  ## Run tests with coverage report
	pytest $(TESTS)/ -v --cov=$(SRC) --cov-report=term-missing --cov-report=html
	@echo "HTML report: htmlcov/index.html"

lint:  ## Lint code with flake8 and mypy
	flake8 $(SRC)/ --max-line-length=100
	mypy $(SRC)/ --ignore-missing-imports

format:  ## Format code with black
	black $(SRC)/ $(TESTS)/ --line-length=100

format-check:  ## Check formatting without modifying
	black $(SRC)/ $(TESTS)/ --line-length=100 --check

clean:  ## Remove build artifacts and cache
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .mypy_cache/

demo:  ## Run a dry-run demo deployment
	deploy_server --config config/templates/nginx.yml --dry-run --verbose

.DEFAULT_GOAL := help

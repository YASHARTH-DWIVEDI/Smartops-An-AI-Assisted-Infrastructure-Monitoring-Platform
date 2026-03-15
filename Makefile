.PHONY: install api agent dashboard test coverage lint format docker-up docker-down seed help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install all dependencies
	pip install -r requirements.txt

setup:  ## First-time setup (copy .env, install deps, create log dir)
	cp -n .env.example .env || true
	pip install -r requirements.txt
	mkdir -p logs
	@echo "✅ Setup complete. Edit .env then run: make api"

api:  ## Start the FastAPI backend
	cd api && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

agent:  ## Start the monitoring agent
	cd agent && python agent.py

dashboard:  ## Start the Streamlit dashboard
	cd dashboard && streamlit run app.py --server.port 8501

all:  ## Start all services (requires tmux or run in separate terminals)
	bash scripts/run_all.sh

seed:  ## Seed database with test data
	python scripts/seed_data.py --servers 2 --hours 6

test:  ## Run test suite
	pytest tests/ -v --tb=short

coverage:  ## Run tests with coverage report
	pytest tests/ -v --cov=. --cov-report=term-missing --cov-report=html

lint:  ## Lint with flake8
	flake8 api/ agent/ ai_engine/ shared/ --max-line-length=100 --extend-ignore=E203

format:  ## Format with black
	black api/ agent/ ai_engine/ shared/ tests/ --line-length=100

docker-up:  ## Start with Docker Compose
	docker-compose up --build

docker-down:  ## Stop Docker Compose services
	docker-compose down

docker-logs:  ## Tail Docker logs
	docker-compose logs -f

clean:  ## Remove build artifacts and cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage smartops.db

.DEFAULT_GOAL := help

# ── Additional targets ───────────────────────
test-new:  ## Run only new/added tests
	pytest tests/test_server_service.py tests/test_incident_service.py \
	       tests/test_auth.py tests/test_retry.py tests/test_log_collector.py -v

docker-postgres:  ## Start only postgres (for local dev with local API)
	docker-compose up postgres -d

gen-key:  ## Generate a random API key
	@python3 -c "import secrets; print(secrets.token_urlsafe(32))"

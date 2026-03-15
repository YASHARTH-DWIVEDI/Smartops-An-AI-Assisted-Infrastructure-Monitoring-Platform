# ─────────────────────────────────────────────────────────────────────────────
#  SmartOps — Makefile
#  Convenience targets for local development
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: help install api agent dashboard test lint clean docker-up docker-down

# Default target
help:
	@echo ""
	@echo "  SmartOps Development Commands"
	@echo "  ─────────────────────────────"
	@echo "  make install      Install Python dependencies"
	@echo "  make api          Start the FastAPI backend"
	@echo "  make agent        Start the monitoring agent"
	@echo "  make dashboard    Start the Streamlit dashboard"
	@echo "  make test         Run the test suite"
	@echo "  make lint         Run ruff linter"
	@echo "  make clean        Remove __pycache__ and .db files"
	@echo "  make docker-up    Start all services via Docker Compose"
	@echo "  make docker-down  Stop all Docker services"
	@echo ""

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	pip install --upgrade pip
	pip install -r requirements.txt
	cp -n .env.example .env || true
	mkdir -p logs

# ── Run services ──────────────────────────────────────────────────────────────

api:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

agent:
	python -m agent.agent

dashboard:
	streamlit run dashboard/app.py

# Run all three in parallel (requires tmux or multiple terminals in CI)
run-all:
	@echo "Starting all services in background..."
	@uvicorn api.main:app --host 0.0.0.0 --port 8000 &
	@sleep 2
	@python -m agent.agent &
	@streamlit run dashboard/app.py

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	pytest tests/ -v

test-coverage:
	pytest tests/ --cov=. --cov-report=html --cov-report=term-missing

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	ruff check . --fix

format:
	ruff format .

# ── Docker ────────────────────────────────────────────────────────────────────

docker-up:
	docker-compose -f docker/docker-compose.yml up --build

docker-up-d:
	docker-compose -f docker/docker-compose.yml up --build -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

docker-logs:
	docker-compose -f docker/docker-compose.yml logs -f

# ── Cleanup ───────────────────────────────────────────────────────────────────

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.db" -delete
	rm -rf .pytest_cache htmlcov .coverage
	@echo "Clean complete."

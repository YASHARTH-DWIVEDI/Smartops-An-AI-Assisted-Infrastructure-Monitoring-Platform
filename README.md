# 🖥️ SmartOps — AI-Assisted Infrastructure Monitoring Platform

SmartOps is a production-grade internal IT monitoring system for infrastructure teams. It collects real-time metrics from Linux servers, stores them in a database, surfaces them through a live dashboard, and uses an AI module to diagnose anomalies.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        SmartOps Platform                        │
│                                                                 │
│  ┌──────────────┐    HTTP POST     ┌───────────────────────┐   │
│  │  Agent(s)    │ ──────────────→  │   FastAPI Backend     │   │
│  │  (psutil)    │                  │   /api/v1/metrics     │   │
│  │  runs every  │                  │   /api/v1/servers     │   │
│  │  10 seconds  │                  │   /api/v1/alerts      │   │
│  └──────────────┘                  └──────────┬────────────┘   │
│                                               │                 │
│                                        SQLite / PostgreSQL      │
│                                               │                 │
│  ┌──────────────┐    REST API       ┌──────────┴────────────┐   │
│  │  Streamlit   │ ←──────────────── │   Database Layer      │   │
│  │  Dashboard   │                   │   SQLAlchemy ORM      │   │
│  └──────┬───────┘                   └───────────────────────┘   │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐                                               │
│  │  AI Engine   │  (Gemini / OpenAI / Rule-based fallback)      │
│  │  Diagnostic  │                                               │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| `agent/` | Python + psutil | Collect & ship metrics |
| `api/` | FastAPI + SQLAlchemy | Receive, validate, store metrics |
| `database/` | SQLite (dev) / PostgreSQL (prod) | Persistent storage |
| `dashboard/` | Streamlit | Visualise metrics & alerts |
| `ai_engine/` | Gemini / Rule-based | Diagnose anomalies |
| `docker/` | Docker + Compose | Container orchestration |

---

## Quick Start (Local)

### 1. Prerequisites

```bash
python 3.10+
pip
(optional) docker & docker-compose
```

### 2. Clone & install dependencies

```bash
git clone https://github.com/yourorg/smartops.git
cd smartops
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your values (API keys, DB URL, etc.)
```

### 4. Start the Backend API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Start the Monitoring Agent

```bash
python -m agent.agent
```

### 6. Start the Dashboard

```bash
streamlit run dashboard/app.py
```

### 7. (Optional) Docker Compose

```bash
docker-compose -f docker/docker-compose.yml up --build
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./smartops.db` | DB connection string |
| `API_HOST` | `http://localhost:8000` | Backend URL used by agent |
| `AGENT_INTERVAL` | `10` | Seconds between metric collections |
| `SERVER_NAME` | hostname | Agent identity |
| `GEMINI_API_KEY` | — | Optional: Gemini AI key |
| `OPENAI_API_KEY` | — | Optional: OpenAI key |
| `ALERT_EMAIL_FROM` | — | SMTP from address |
| `ALERT_EMAIL_TO` | — | Alert recipient |
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_PASSWORD` | — | SMTP password |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/metrics/` | Ingest metrics from agent |
| `GET` | `/api/v1/metrics/{server}` | Query server history |
| `GET` | `/api/v1/servers/` | List all servers |
| `GET` | `/api/v1/alerts/` | List recent alerts |
| `GET` | `/api/v1/diagnose/{server}` | AI diagnostic report |
| `GET` | `/health` | Health check |

---

## Alert Thresholds

| Metric | Threshold |
|--------|-----------|
| CPU | > 90% |
| Memory | > 90% |
| Disk | > 85% |

---

## Project Structure

```
smartops/
├── agent/
│   ├── __init__.py
│   ├── agent.py          # Main agent loop
│   ├── collector.py      # psutil metric collection
│   └── sender.py         # HTTP sender with retry logic
├── api/
│   ├── __init__.py
│   ├── main.py           # FastAPI app entry point
│   ├── dependencies.py   # DB session injection
│   ├── routers/
│   │   ├── metrics.py
│   │   ├── servers.py
│   │   └── alerts.py
│   ├── models/
│   │   └── db_models.py  # SQLAlchemy ORM models
│   ├── services/
│   │   ├── metric_service.py
│   │   └── alert_service.py
│   └── middleware/
│       └── logging_middleware.py
├── database/
│   ├── __init__.py
│   └── session.py        # DB engine & session factory
├── dashboard/
│   ├── app.py            # Streamlit dashboard
│   └── charts.py         # Reusable chart helpers
├── ai_engine/
│   ├── __init__.py
│   ├── diagnostics.py    # Main AI dispatcher
│   ├── gemini_client.py  # Gemini integration
│   └── rule_engine.py    # Rule-based fallback
├── config/
│   └── settings.py       # Pydantic settings
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.agent
│   └── docker-compose.yml
├── tests/
│   ├── test_agent.py
│   ├── test_api.py
│   └── test_ai_engine.py
├── .env.example
├── requirements.txt
└── README.md
```

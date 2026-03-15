# SmartOps 🖥️ — AI-Assisted Infrastructure Monitoring Platform

> A production-like internal IT monitoring system for infrastructure teams.
> Collects server metrics, stores them in a database, visualizes trends, fires alerts,
> and uses AI to diagnose anomalies.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-red.svg)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/docker-compose-blue.svg)](https://docs.docker.com/compose/)

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         SmartOps Platform                           │
│                                                                     │
│  ┌───────────┐    HTTP POST     ┌──────────────────────────────┐   │
│  │  Agent    │ ──────────────►  │  FastAPI Backend             │   │
│  │  (psutil) │  /api/metrics    │  - Validate metrics          │   │
│  │  every 10s│                  │  - Store to DB               │   │
│  └───────────┘                  │  - Fire alerts               │   │
│                                 │  - Query history             │   │
│  ┌───────────┐    HTTP GET      └────────────┬─────────────────┘   │
│  │ Streamlit │ ◄────────────────             │                      │
│  │ Dashboard │  /api/metrics                 ▼                      │
│  │           │                  ┌──────────────────────────────┐   │
│  └─────┬─────┘                  │  SQLite / PostgreSQL DB       │   │
│        │                        │  metrics table + alerts       │   │
│        │ AI Diagnose            └──────────────────────────────┘   │
│        ▼                                                            │
│  ┌───────────┐                                                      │
│  │ AI Engine │  Gemini API (fallback: rule-based)                   │
│  │           │  - Analyze anomalies                                 │
│  │           │  - Suggest fixes                                     │
│  └───────────┘                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
smartops/
├── agent/
│   ├── agent.py          # Main agent loop (runs every 10s)
│   ├── collector.py      # psutil metric collection
│   ├── sender.py         # HTTP sender with retry logic
│   └── config.py         # Agent configuration
├── api/
│   ├── main.py           # FastAPI app entry point
│   ├── config.py         # API configuration
│   ├── routers/
│   │   ├── metrics.py    # POST /metrics, GET /metrics
│   │   └── alerts.py     # GET /alerts
│   ├── models/
│   │   └── schemas.py    # Pydantic request/response schemas
│   ├── database/
│   │   ├── models.py     # SQLAlchemy ORM models
│   │   └── session.py    # DB session management
│   └── services/
│       ├── metrics_service.py  # Business logic for metrics
│       └── alert_service.py   # Alert evaluation & storage
├── dashboard/
│   └── app.py            # Streamlit dashboard
├── ai_engine/
│   ├── diagnostics.py    # Main AI dispatcher
│   ├── gemini_client.py  # Google Gemini integration
│   └── rules.py          # Fallback rule-based engine
├── config/
│   └── settings.yml      # Central configuration file
├── docker/
│   ├── Dockerfile.api    # API container
│   ├── Dockerfile.agent  # Agent container
│   └── docker-compose.yml
├── tests/
│   ├── test_collector.py
│   ├── test_api.py
│   └── test_ai_engine.py
├── docs/
│   └── architecture.md
├── scripts/
│   ├── run_all.sh        # Start everything locally
│   └── seed_data.py      # Generate test data
├── .env.example
├── requirements.txt
├── requirements-agent.txt
└── docker-compose.yml    # Root compose file
```

---

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/yourname/smartops.git
cd smartops
cp .env.example .env
docker-compose up --build
```

Services:
- API:       http://localhost:8000
- Dashboard: http://localhost:8501
- API Docs:  http://localhost:8000/docs

### Option 2: Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — add GEMINI_API_KEY if you have one

# 3. Start the API
cd api && uvicorn main:app --reload --port 8000

# 4. Start the dashboard (new terminal)
cd dashboard && streamlit run app.py --server.port 8501

# 5. Start the monitoring agent (new terminal)
cd agent && python agent.py

# 6. (Optional) Seed test data
python scripts/seed_data.py
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SMARTOPS_ENV` | `development` | Environment name |
| `DATABASE_URL` | `sqlite:///./smartops.db` | Database connection string |
| `API_HOST` | `0.0.0.0` | API bind host |
| `API_PORT` | `8000` | API port |
| `AGENT_API_URL` | `http://localhost:8000` | API URL for agent |
| `AGENT_INTERVAL` | `10` | Metric collection interval (seconds) |
| `AGENT_SERVER_NAME` | `hostname` | Server identifier |
| `GEMINI_API_KEY` | `` | Google Gemini API key (optional) |
| `ALERT_CPU_THRESHOLD` | `90` | CPU alert threshold % |
| `ALERT_MEMORY_THRESHOLD` | `90` | Memory alert threshold % |
| `ALERT_DISK_THRESHOLD` | `85` | Disk alert threshold % |
| `SMTP_HOST` | `` | SMTP host for email alerts |
| `SMTP_PORT` | `587` | SMTP port |
| `ALERT_EMAIL_FROM` | `` | Alert sender email |
| `ALERT_EMAIL_TO` | `` | Alert recipient email |

---

## 📊 API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/metrics` | Receive metrics from agent |
| GET  | `/api/metrics?server=&limit=100` | Query metrics history |
| GET  | `/api/metrics/servers` | List all monitored servers |
| GET  | `/api/metrics/latest` | Latest metrics per server |
| GET  | `/api/alerts?server=&resolved=` | Query alerts |
| GET  | `/api/alerts/summary` | Alert counts summary |
| POST | `/api/ai/diagnose` | AI anomaly diagnosis |
| GET  | `/health` | API health check |

---

## 🤖 AI Diagnostic Module

The AI engine works in two modes:

1. **Gemini mode** (requires `GEMINI_API_KEY`): Sends metric context to Google Gemini
   for intelligent natural-language diagnosis and remediation steps.

2. **Rule-based fallback** (always available): Pattern matches against known thresholds
   and returns structured diagnostic output with probable causes and commands to run.

---

## 🧪 Running Tests

```bash
pytest tests/ -v --tb=short
```

---

## 📝 License

MIT

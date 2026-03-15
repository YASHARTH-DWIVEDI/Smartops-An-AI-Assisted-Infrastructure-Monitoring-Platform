# SmartOps Architecture

## System Overview

SmartOps is a production-like infrastructure monitoring platform with five components:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          SmartOps Platform                              │
│                                                                         │
│  Monitored Servers                 SmartOps Core                        │
│  ────────────────                  ─────────────                        │
│                                                                         │
│  ┌──────────────┐  HTTP POST      ┌─────────────────────────────────┐  │
│  │  Agent       │ ──────────────► │  FastAPI Backend                │  │
│  │  (psutil)    │  /api/metrics   │                                 │  │
│  │  every 10s   │                 │  ┌───────────┐ ┌─────────────┐ │  │
│  └──────────────┘                 │  │ Routers   │ │  Services   │ │  │
│                                   │  │ /metrics  │ │  Metrics    │ │  │
│  ┌──────────────┐                 │  │ /alerts   │ │  Alerts     │ │  │
│  │  Agent       │                 │  │ /ai       │ │             │ │  │
│  │  (server 2)  │                 │  └─────┬─────┘ └──────┬──────┘ │  │
│  └──────────────┘                 │        │               │        │  │
│                                   │        ▼               ▼        │  │
│                                   │  ┌─────────────────────────┐   │  │
│                                   │  │  SQLite / PostgreSQL     │   │  │
│                                   │  │  metrics + alerts tables │   │  │
│                                   │  └─────────────────────────┘   │  │
│                                   └────────────┬────────────────────┘  │
│                                                │                        │
│  ┌──────────────┐  HTTP GET                    │                        │
│  │  Streamlit   │ ◄────────────────────────────┘                        │
│  │  Dashboard   │  GET /api/metrics                                     │
│  │              │  GET /api/alerts                                      │
│  └──────┬───────┘  POST /api/ai/diagnose                               │
│         │                                                               │
│         │ POST /api/ai/diagnose          ┌──────────────────────┐      │
│         └──────────────────────────────► │  AI Engine           │      │
│                                          │  ┌────────────────┐  │      │
│                                          │  │ Gemini API     │  │      │
│                                          │  │ (if key set)   │  │      │
│                                          │  └───────┬────────┘  │      │
│                                          │          │ fallback   │      │
│                                          │  ┌───────▼────────┐  │      │
│                                          │  │ Rule Engine    │  │      │
│                                          │  │ (always avail) │  │      │
│                                          │  └────────────────┘  │      │
│                                          └──────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Monitoring Agent (`agent/`)

The agent is a lightweight Python script that runs on each monitored server.

**Key files:**
- `agent.py` — main loop, signal handling, graceful shutdown
- `collector.py` — psutil-based metric collection
- `sender.py` — HTTP sender with tenacity retry and offline queue
- `config.py` — reads from env vars and settings.yml

**Collection cycle (every 10 seconds):**
1. `MetricCollector.collect()` — gathers CPU, memory, disk, network, processes
2. `MetricSender.send()` — POST to `/api/metrics` with retry backoff
3. If API is unreachable, queues up to 100 metrics in memory
4. On reconnection, flushes the queue automatically

**Retry strategy:**
- 3 attempts by default
- Exponential backoff: 5s → 10s → 20s
- Jitter applied to avoid thundering herd

### 2. FastAPI Backend (`api/`)

Layered architecture: routers → services → database.

```
api/
├── main.py           # App factory, middleware, lifespan hooks
├── config.py         # Pydantic Settings (reads .env)
├── routers/          # HTTP endpoint definitions only
│   ├── metrics.py    # POST + GET /api/metrics
│   ├── alerts.py     # GET /api/alerts
│   └── ai.py         # POST /api/ai/diagnose
├── models/
│   └── schemas.py    # Pydantic v2 input/output schemas
├── database/
│   ├── models.py     # SQLAlchemy ORM (MetricRecord, AlertRecord)
│   └── session.py    # Engine + session factory + FastAPI dep
└── services/
    ├── metrics_service.py  # DB CRUD + query logic
    └── alert_service.py    # Threshold evaluation + email
```

**Request flow:**
```
POST /api/metrics
  → MetricPayload (Pydantic validation)
  → MetricsService.create(db, payload)   — writes to metrics table
  → AlertService.evaluate(db, payload)   — checks thresholds
      → if breach: AlertRecord created
      → if email configured: sends SMTP notification
  → Response: SuccessResponse
```

### 3. Database Layer (`api/database/`)

**SQLite** by default (zero setup), **PostgreSQL** for production.

**Schema:**

```sql
-- metrics table
CREATE TABLE metrics (
    id              INTEGER PRIMARY KEY,
    server_name     TEXT    NOT NULL,
    timestamp       DATETIME NOT NULL,
    cpu_percent     REAL    NOT NULL,
    memory_percent  REAL    NOT NULL,
    memory_used_mb  REAL,
    memory_total_mb REAL,
    disk_percent    REAL    NOT NULL,
    disk_used_gb    REAL,
    disk_total_gb   REAL,
    net_bytes_sent  INTEGER,
    net_bytes_recv  INTEGER,
    uptime_seconds  REAL,
    load_avg_1m     REAL,
    load_avg_5m     REAL,
    load_avg_15m    REAL,
    process_count   INTEGER,
    top_processes_json TEXT
);
CREATE INDEX ix_metrics_server_timestamp ON metrics(server_name, timestamp);

-- alerts table
CREATE TABLE alerts (
    id              INTEGER PRIMARY KEY,
    server_name     TEXT    NOT NULL,
    timestamp       DATETIME NOT NULL,
    alert_type      TEXT    NOT NULL,  -- cpu|memory|disk
    severity        TEXT    NOT NULL,  -- warning|critical
    metric_value    REAL    NOT NULL,
    threshold_value REAL    NOT NULL,
    message         TEXT    NOT NULL,
    resolved        BOOLEAN DEFAULT FALSE,
    resolved_at     DATETIME,
    email_sent      BOOLEAN DEFAULT FALSE
);
```

### 4. Dashboard (`dashboard/app.py`)

Single-file Streamlit app. No backend framework needed.

**Tabs:**
1. **Live Metrics** — gauge charts per server (CPU/MEM/DISK)
2. **History Charts** — time-series Plotly charts (6h / 24h / 48h)
3. **Alerts** — active + resolved alerts panel
4. **AI Diagnosis** — on-demand analysis with AI engine

Data is fetched via `requests` to the FastAPI backend. Results are cached
with `@st.cache_data(ttl=30)` to avoid hammering the API.

### 5. AI Diagnostic Engine (`ai_engine/`)

```
DiagnosticsEngine.diagnose(metrics, server_name)
    ├── Try: GeminiClient.diagnose()     if GEMINI_API_KEY set
    │       → Sends structured prompt to gemini-pro
    │       → Parses JSON response
    │       → Returns DiagnoseResponse
    │
    └── Fallback: RuleBasedEngine.diagnose()
            → Pattern matches metric values against thresholds
            → Returns curated causes + Linux commands
```

**Rule engine thresholds:**
| Metric | Warning | Critical |
|--------|---------|----------|
| CPU    | ≥ 75%   | ≥ 90%    |
| Memory | ≥ 75%   | ≥ 90%    |
| Disk   | ≥ 70%   | ≥ 85%    |

## Data Flow Diagram

```
Agent (10s)
  │ POST /api/metrics {cpu, mem, disk, ...}
  ▼
FastAPI Router (metrics.py)
  │ Pydantic validation
  ▼
MetricsService.create()
  │ INSERT INTO metrics
  ▼
AlertService.evaluate()
  │ Check cpu >= 90% | mem >= 90% | disk >= 85%
  ├── [breach] INSERT INTO alerts
  │            [email configured] → SMTP
  └── [ok] skip
  │
Dashboard polls GET /api/metrics?server=X&hours=6
  │
Plotly time-series charts rendered in browser
  │
User clicks "Run Diagnosis"
  │ POST /api/ai/diagnose
  │
DiagnosticsEngine
  ├── Gemini API → natural language analysis
  └── Rules engine → structured causes + commands
```

## Deployment Options

### Local Development
```bash
make setup && make all
```

### Docker Compose (Recommended)
```bash
docker-compose up --build
```

### Production (PostgreSQL)
```env
DATABASE_URL=postgresql://user:pass@db:5432/smartops
SMARTOPS_ENV=production
```

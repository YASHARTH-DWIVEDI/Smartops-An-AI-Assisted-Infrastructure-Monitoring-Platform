#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# SmartOps — Run all components locally
# Usage: ./scripts/run_all.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
title() { echo -e "\n${CYAN}══ $* ══${NC}\n"; }

# ── Prerequisites ─────────────────────────────
title "Checking Prerequisites"

command -v python3 &>/dev/null || { echo "❌ python3 required"; exit 1; }
info "Python $(python3 --version)"

if [[ ! -f ".env" ]]; then
    warn ".env not found — copying from .env.example"
    cp .env.example .env
fi

# ── Install dependencies ──────────────────────
title "Installing Dependencies"
pip install -r requirements.txt -q
info "Dependencies installed"

# ── Create log dir ────────────────────────────
mkdir -p logs

# ── Start API ─────────────────────────────────
title "Starting API Server"
cd "$ROOT/api"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
info "API started (pid=$API_PID)"
cd "$ROOT"

# Wait for API to be ready
echo -n "Waiting for API..."
for i in {1..15}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo " ready!"
        break
    fi
    echo -n "."
    sleep 1
done

# ── Start Dashboard ───────────────────────────
title "Starting Dashboard"
cd "$ROOT/dashboard"
streamlit run app.py --server.port 8501 --server.headless true &
DASH_PID=$!
info "Dashboard started (pid=$DASH_PID)"
cd "$ROOT"

# ── Start Agent ───────────────────────────────
title "Starting Monitoring Agent"
cd "$ROOT/agent"
python agent.py &
AGENT_PID=$!
info "Agent started (pid=$AGENT_PID)"
cd "$ROOT"

# ── Summary ───────────────────────────────────
echo ""
echo "────────────────────────────────────────────"
echo "  🟢 SmartOps is running"
echo ""
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Dashboard: http://localhost:8501"
echo ""
echo "  PIDs: API=$API_PID  Dashboard=$DASH_PID  Agent=$AGENT_PID"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "────────────────────────────────────────────"

# ── Cleanup on exit ───────────────────────────
cleanup() {
    echo ""
    warn "Stopping all services..."
    kill $API_PID $DASH_PID $AGENT_PID 2>/dev/null || true
    info "All stopped."
}
trap cleanup INT TERM

# Wait for any child to exit
wait

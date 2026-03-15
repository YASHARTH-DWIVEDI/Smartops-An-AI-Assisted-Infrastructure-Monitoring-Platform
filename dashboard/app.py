"""
SmartOps Dashboard v1.1 — Production NOC Interface

New panels:
  - Server inventory with registration info
  - Incident history with severity + MTTR
  - Log viewer (syslog / nginx / docker)
  - Health score per server
  - API auth header support
"""

import os, sys, time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API_URL      = os.getenv("AGENT_API_URL", "http://localhost:8000")
API_KEY      = os.getenv("SMARTOPS_API_KEY", "")
REFRESH_SEC  = int(os.getenv("DASHBOARD_REFRESH", "30"))

st.set_page_config(
    page_title="SmartOps NOC",
    page_icon="🖥️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@300;400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0d1117; color: #e6edf3; }
.card {
  background: #161b22; border: 1px solid #30363d;
  border-radius: 10px; padding: 18px; margin-bottom: 8px;
}
.mono { font-family: 'JetBrains Mono', monospace; }
.badge-healthy  { background:#1a4731; color:#3fb950; border-radius:4px; padding:2px 8px; font-size:.75rem; font-weight:600; }
.badge-warning  { background:#3a2d05; color:#d29922; border-radius:4px; padding:2px 8px; font-size:.75rem; font-weight:600; }
.badge-critical { background:#3d1a1a; color:#f85149; border-radius:4px; padding:2px 8px; font-size:.75rem; font-weight:600; }
.badge-offline  { background:#21262d; color:#8b949e; border-radius:4px; padding:2px 8px; font-size:.75rem; font-weight:600; }
.incident-open    { border-left:3px solid #f85149; background:rgba(248,81,73,.08); padding:10px; margin:4px 0; border-radius:4px; }
.incident-resolved{ border-left:3px solid #3fb950; background:rgba(63,185,80,.05); padding:10px; margin:4px 0; border-radius:4px; }
.log-error  { color:#f85149; font-family:'JetBrains Mono',monospace; font-size:.78rem; }
.log-warn   { color:#d29922; font-family:'JetBrains Mono',monospace; font-size:.78rem; }
.log-info   { color:#8b949e; font-family:'JetBrains Mono',monospace; font-size:.78rem; }
</style>
""", unsafe_allow_html=True)

CHART = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#8b949e", size=11), margin=dict(l=0,r=0,t=30,b=0),
    xaxis=dict(gridcolor="#21262d"), yaxis=dict(gridcolor="#21262d"),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)

def _headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h

def _get(path, params=None, timeout=8):
    try:
        r = requests.get(f"{API_URL}{path}", params=params, headers=_headers(), timeout=timeout)
        return r.json() if r.ok else []
    except Exception:
        return []

def _post(path, body, timeout=30):
    try:
        r = requests.post(f"{API_URL}{path}", json=body, headers=_headers(), timeout=timeout)
        return r.json() if r.ok else None
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(ttl=REFRESH_SEC)
def fetch_servers():    return _get("/api/servers") or []
@st.cache_data(ttl=REFRESH_SEC)
def fetch_latest():     return _get("/api/metrics/latest") or []
@st.cache_data(ttl=REFRESH_SEC)
def fetch_history(srv, lim=300, hrs=6):
    data = _get("/api/metrics", {"server": srv, "limit": lim, "hours": hrs})
    if data:
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df.sort_values("timestamp")
    return pd.DataFrame()
@st.cache_data(ttl=REFRESH_SEC)
def fetch_incidents(srv=None, resolved=None, limit=100):
    p = {"limit": limit}
    if srv: p["server"] = srv
    if resolved is not None: p["resolved"] = str(resolved).lower()
    return _get("/api/incidents", p) or []
@st.cache_data(ttl=REFRESH_SEC)
def fetch_logs(srv=None, level=None, limit=200):
    p = {"limit": limit}
    if srv: p["server"] = srv
    if level: p["level"] = level
    return _get("/api/logs", p) or []
@st.cache_data(ttl=60)
def fetch_incident_stats(srv=None):
    p = {}
    if srv: p["server"] = srv
    return _get("/api/incidents/stats", p) or {}

def health_check():
    try:
        r = requests.get(f"{API_URL}/health", timeout=3)
        return r.ok
    except Exception:
        return False

def pct_color(v, warn=75, crit=90):
    if v >= crit: return "#f85149"
    if v >= warn: return "#d29922"
    return "#3fb950"

def score_color(s):
    if s >= 80: return "#3fb950"
    if s >= 50: return "#d29922"
    return "#f85149"

def badge(status):
    icons = {"healthy":"🟢","warning":"🟡","critical":"🔴","offline":"⚫"}
    return icons.get(status,"⚪")

def gauge(val, title, max_val=100, warn=75, crit=90):
    color = pct_color(val, warn, crit)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=val,
        number={"suffix":"%","font":{"color":color,"size":26}},
        title={"text":title,"font":{"color":"#8b949e","size":11}},
        gauge={
            "axis":{"range":[0,max_val],"tickcolor":"#30363d"},
            "bar":{"color":color,"thickness":0.22},
            "bgcolor":"#21262d","bordercolor":"#30363d",
            "steps":[
                {"range":[0,warn],"color":"#0d1117"},
                {"range":[warn,crit],"color":"rgba(210,153,34,.12)"},
                {"range":[crit,100],"color":"rgba(248,81,73,.12)"},
            ],
            "threshold":{"line":{"color":"#f85149","width":2},"thickness":0.75,"value":crit},
        },
    ))
    fig.update_layout(height=170, **CHART)
    return fig

def line_chart(df, cols, colors, title, y_suffix="%"):
    fig = go.Figure()
    for col, color in zip(cols, colors):
        if col not in df.columns: continue
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df[col],
            name=col.replace("_percent","").replace("_"," ").title(),
            line=dict(color=color, width=1.8),
            fill="tozeroy",
            fillcolor=color+"18",
            hovertemplate=f"%{{y:.1f}}{y_suffix}<extra></extra>",
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=12, color="#e6edf3")),
        height=240, yaxis_range=[0,100],
        yaxis_ticksuffix=y_suffix, hovermode="x unified", **CHART,
    )
    return fig

# ════════════════════════ SIDEBAR ════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ SmartOps NOC")
    st.markdown("---")
    api_ok = health_check()
    st.markdown(f"**API:** {'🟢 Online' if api_ok else '🔴 Offline'}")
    if API_KEY:
        st.markdown("**Auth:** 🔒 Enabled")
    st.markdown(f"`{API_URL}`")
    st.markdown("---")

    servers_list = [s["hostname"] for s in fetch_servers()]
    sel_server = st.selectbox("🖥️ Server", ["All"] + servers_list)
    hours_back = st.slider("📅 History window (h)", 1, 48, 6)

    st.markdown("---")
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()
    st.markdown(f"*Refresh: {REFRESH_SEC}s*")
    st.markdown(f"*{datetime.now().strftime('%H:%M:%S')}*")

if not api_ok:
    st.error("⚠️ Cannot reach SmartOps API.")
    st.code("cd api && uvicorn main:app --port 8000", language="bash")
    st.stop()

st.markdown("# 🖥️ SmartOps NOC Dashboard")
st.markdown("---")

# ── KPI row ──────────────────────────────────────────────
latest = fetch_latest()
srv_data = fetch_servers()
all_incidents = fetch_incidents(limit=500)
open_incidents = [i for i in all_incidents if not i.get("resolved")]
critical_inc   = [i for i in open_incidents if i.get("severity") == "critical"]

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"""<div class="card" style="text-align:center">
      <div style="font-size:2rem;font-weight:700;color:#58a6ff">{len(srv_data)}</div>
      <div style="color:#8b949e;font-size:.8rem;text-transform:uppercase;letter-spacing:1px">Servers</div>
    </div>""", unsafe_allow_html=True)
with k2:
    healthy_count = sum(1 for s in srv_data if s.get("status") == "healthy")
    st.markdown(f"""<div class="card" style="text-align:center">
      <div style="font-size:2rem;font-weight:700;color:#3fb950">{healthy_count}</div>
      <div style="color:#8b949e;font-size:.8rem;text-transform:uppercase;letter-spacing:1px">Healthy</div>
    </div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""<div class="card" style="text-align:center">
      <div style="font-size:2rem;font-weight:700;color:#f85149">{len(open_incidents)}</div>
      <div style="color:#8b949e;font-size:.8rem;text-transform:uppercase;letter-spacing:1px">Open Incidents</div>
    </div>""", unsafe_allow_html=True)
with k4:
    st.markdown(f"""<div class="card" style="text-align:center">
      <div style="font-size:2rem;font-weight:700;color:#d29922">{len(critical_inc)}</div>
      <div style="color:#8b949e;font-size:.8rem;text-transform:uppercase;letter-spacing:1px">Critical</div>
    </div>""", unsafe_allow_html=True)

st.markdown("")

# ════════════════════════ TABS ════════════════════════
tab_servers, tab_metrics, tab_history, tab_incidents, tab_logs, tab_ai = st.tabs([
    "🖥️ Servers", "📊 Live Metrics", "📉 History", "🚨 Incidents", "📋 Logs", "🤖 AI Diagnosis"
])

# ── Tab: Server Inventory ─────────────────────────────
with tab_servers:
    st.markdown("#### Registered Server Inventory")
    if not srv_data:
        st.info("No servers registered yet. Start the monitoring agent.")
    else:
        for srv in srv_data:
            status  = srv.get("status","unknown")
            score   = srv.get("health_score", 100.0) or 100.0
            last    = srv.get("last_seen","")[:19] if srv.get("last_seen") else "Never"
            ip      = srv.get("ip_address","—")
            os_info = f"{srv.get('os_name','')} {srv.get('os_version','')}".strip() or "—"
            cores   = srv.get("cpu_cores","—")
            mem_gb  = round(srv.get("memory_total_mb", 0) / 1024, 1) if srv.get("memory_total_mb") else "—"
            agent_v = srv.get("agent_version","—")

            badge_html = f'<span class="badge-{status}">{status.upper()}</span>'
            score_c    = score_color(score)

            st.markdown(f"""
            <div class="card">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <span style="font-size:1.05rem;font-weight:600">{badge(status)} {srv['hostname']}</span>
                  &nbsp;{badge_html}
                  <span style="margin-left:12px;font-family:'JetBrains Mono',monospace;
                    color:{score_c};font-size:.9rem;font-weight:700">
                    Health: {score:.0f}/100
                  </span>
                </div>
                <div style="color:#8b949e;font-size:.78rem">Last seen: {last}</div>
              </div>
              <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-top:12px;
                color:#8b949e;font-size:.78rem">
                <div><b style="color:#e6edf3">IP</b><br>{ip}</div>
                <div><b style="color:#e6edf3">OS</b><br>{os_info}</div>
                <div><b style="color:#e6edf3">CPU Cores</b><br>{cores}</div>
                <div><b style="color:#e6edf3">RAM</b><br>{mem_gb} GB</div>
                <div><b style="color:#e6edf3">Agent</b><br>v{agent_v}</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

# ── Tab: Live Metrics ──────────────────────────────────
with tab_metrics:
    srv_filter = None if sel_server == "All" else sel_server
    display = [s for s in latest if not srv_filter or s["server_name"] == srv_filter]

    if not display:
        st.info("No metrics yet. Start the monitoring agent.")
    else:
        for srv in display:
            sname = srv["server_name"]
            sco   = srv.get("health_score") or 100.0
            st.markdown(
                f"#### {badge(srv.get('status','healthy'))} {sname} "
                f"<span style='color:{score_color(sco)};font-size:.85rem'>"
                f"Score: {sco:.0f}/100</span>",
                unsafe_allow_html=True,
            )
            g1, g2, g3 = st.columns(3)
            with g1: st.plotly_chart(gauge(srv.get("cpu_percent",0),"CPU"), use_container_width=True)
            with g2: st.plotly_chart(gauge(srv.get("memory_percent",0),"Memory"), use_container_width=True)
            with g3: st.plotly_chart(gauge(srv.get("disk_percent",0),"Disk",crit=85), use_container_width=True)
            st.markdown("---")

# ── Tab: History Charts ─────────────────────────────────
with tab_history:
    chart_servers = [sel_server] if sel_server != "All" else (servers_list or [])

    for sname in chart_servers[:3]:
        df = fetch_history(sname, lim=500, hrs=hours_back)
        if df.empty:
            st.warning(f"No history for {sname}")
            continue

        st.markdown(f"#### 🖥️ {sname}")
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(line_chart(df,["cpu_percent"],["#58a6ff"],f"CPU — {sname}"), use_container_width=True)
        with c2:
            st.plotly_chart(line_chart(df,["memory_percent"],["#3fb950"],f"Memory — {sname}"), use_container_width=True)
        c3, c4 = st.columns(2)
        with c3:
            st.plotly_chart(line_chart(df,["disk_percent"],["#d29922"],f"Disk — {sname}"), use_container_width=True)
        with c4:
            if "health_score" in df.columns and df["health_score"].notna().any():
                fig = go.Figure(go.Scatter(
                    x=df["timestamp"], y=df["health_score"],
                    fill="tozeroy", fillcolor="#58a6ff14",
                    line=dict(color="#58a6ff", width=1.8),
                ))
                fig.update_layout(
                    title=dict(text=f"Health Score — {sname}", font=dict(size=12,color="#e6edf3")),
                    height=240, yaxis_range=[0,100], **CHART,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                if "net_bytes_sent" in df.columns:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["net_bytes_sent"]/1024,
                        name="Sent KB", line=dict(color="#bc8cff",width=1.5)))
                    fig.add_trace(go.Scatter(x=df["timestamp"], y=df["net_bytes_recv"]/1024,
                        name="Recv KB", line=dict(color="#79c0ff",width=1.5)))
                    fig.update_layout(title=dict(text=f"Network — {sname}",
                        font=dict(size=12,color="#e6edf3")), height=240, **CHART)
                    st.plotly_chart(fig, use_container_width=True)

        with st.expander(f"Raw data ({len(df)} records)"):
            cols = [c for c in ["timestamp","cpu_percent","memory_percent","disk_percent",
                                 "health_score","health_status","process_count"] if c in df.columns]
            st.dataframe(df[cols].tail(50), use_container_width=True)
        st.markdown("---")

# ── Tab: Incidents ─────────────────────────────────────
with tab_incidents:
    srv_filter = None if sel_server == "All" else sel_server
    stats = fetch_incident_stats(srv_filter)
    open_inc  = fetch_incidents(srv_filter, resolved=False, limit=100)
    resol_inc = fetch_incidents(srv_filter, resolved=True,  limit=50)

    # Stats row
    if stats:
        s1,s2,s3,s4 = st.columns(4)
        s1.metric("Total Incidents", stats.get("total",0))
        s2.metric("Open",            stats.get("open",0))
        s3.metric("Resolved",        stats.get("resolved",0))
        s4.metric("MTTR",            f"{stats.get('mttr_minutes',0):.1f} min")
        st.markdown("")

    col_open, col_resolved = st.columns([3,2])

    with col_open:
        st.markdown(f"#### 🚨 Open Incidents ({len(open_inc)})")
        if not open_inc:
            st.success("✅ No open incidents.")
        else:
            for inc in open_inc:
                sev_icon = "🔴" if inc.get("severity")=="critical" else "🟡"
                ts = inc.get("timestamp","")[:19]
                ai_summary = inc.get("ai_summary","")
                st.markdown(f"""
                <div class="incident-open">
                  <div><strong>{sev_icon} [{inc.get('alert_type','').upper()}]</strong>
                  {inc.get('server_name','')}
                  <span style="color:#8b949e;font-size:.75rem;margin-left:8px">{ts}</span></div>
                  <div style="color:#8b949e;font-size:.8rem;margin-top:4px">{inc.get('message','')}</div>
                  {f'<div style="color:#d29922;font-size:.78rem;margin-top:4px">AI: {ai_summary}</div>' if ai_summary else ''}
                </div>
                """, unsafe_allow_html=True)

    with col_resolved:
        st.markdown(f"#### ✅ Recently Resolved ({len(resol_inc)})")
        if not resol_inc:
            st.info("No resolved incidents.")
        else:
            for inc in resol_inc[:15]:
                dur = inc.get("duration_seconds",0) or 0
                dur_str = f"{dur/60:.1f}m" if dur >= 60 else f"{dur:.0f}s"
                ts = inc.get("resolved_at","")[:19] or inc.get("timestamp","")[:19]
                st.markdown(f"""
                <div class="incident-resolved">
                  <div style="font-size:.82rem">
                    <strong>{inc.get('alert_type','').upper()}</strong>
                    on <em>{inc.get('server_name','')}</em>
                  </div>
                  <div style="color:#8b949e;font-size:.75rem">
                    Resolved: {ts} · Duration: {dur_str}
                    · By: {inc.get('resolved_by','—')}
                  </div>
                </div>
                """, unsafe_allow_html=True)

# ── Tab: Logs ──────────────────────────────────────────
with tab_logs:
    srv_filter = None if sel_server == "All" else sel_server

    lc1, lc2 = st.columns([3,1])
    with lc2:
        log_level = st.selectbox("Level", ["all","error","warn","info","debug"])
        log_limit = st.slider("Lines", 50, 500, 200)

    with lc1:
        st.markdown("#### 📋 System Log Viewer")

    level_filter = None if log_level == "all" else log_level
    log_entries = fetch_logs(srv_filter, level_filter, log_limit)

    if not log_entries:
        st.info("No log entries found. Agent must be running with log collection enabled.")
    else:
        # Summary stats
        levels = [e.get("level","info") for e in log_entries]
        errors = levels.count("error")
        warns  = levels.count("warn")
        st.markdown(
            f"Showing **{len(log_entries)}** entries | "
            f"🔴 {errors} errors · 🟡 {warns} warnings"
        )

        log_container = st.container()
        with log_container:
            for entry in log_entries[:300]:
                lvl = entry.get("level","info")
                src = entry.get("source","unknown")
                msg = entry.get("message","")[:200]
                ts  = entry.get("timestamp","") or entry.get("received_at","")[:19]
                css = f"log-{lvl}" if lvl in ("error","warn") else "log-info"
                icon = {"error":"🔴","warn":"🟡","info":"⚪","debug":"🔵"}.get(lvl,"⚪")
                st.markdown(
                    f'<div class="{css}">{icon} [{src}] {ts} — {msg}</div>',
                    unsafe_allow_html=True,
                )

# ── Tab: AI Diagnosis ──────────────────────────────────
with tab_ai:
    st.markdown("#### 🤖 AI-Powered Anomaly Diagnosis")
    st.markdown(
        "Select a server and click **Run Diagnosis** to get an analysis "
        "of the current metric snapshot with causes and remediation commands."
    )

    diag_srv = st.selectbox("Server to diagnose", servers_list or [], key="diag_srv")

    if st.button("🔍 Run Diagnosis", type="primary", disabled=not diag_srv):
        target = next((s for s in latest if s["server_name"] == diag_srv), None)
        if not target:
            st.error(f"No recent metrics for {diag_srv}")
        else:
            with st.spinner(f"Analysing {diag_srv}..."):
                result = _post("/api/ai/diagnose", {"server_name": diag_srv, "metrics": target})

            if result and "error" not in result:
                sev = result.get("severity","unknown")
                prov = result.get("provider","unknown")
                sev_colors = {"healthy":"#3fb950","warning":"#d29922","critical":"#f85149"}
                sc = sev_colors.get(sev,"#8b949e")

                st.markdown(f"""
                <div style="border:1px solid {sc};border-radius:8px;padding:16px;
                     background:rgba(0,0,0,.25);margin:12px 0">
                  <div style="font-size:1.05rem;font-weight:700;color:{sc}">
                    {badge(sev)} Severity: {sev.upper()}
                    <span style="font-size:.75rem;color:#8b949e;font-weight:400;margin-left:10px">
                      via {prov}
                    </span>
                  </div>
                  <div style="margin-top:10px;color:#e6edf3">{result.get("summary","")}</div>
                </div>
                """, unsafe_allow_html=True)

                col_c, col_r = st.columns(2)
                with col_c:
                    st.markdown("**🔍 Probable Causes**")
                    for c in result.get("causes",[]):
                        st.markdown(f"- {c}")
                with col_r:
                    st.markdown("**🛠️ Recommendations**")
                    for rec in result.get("recommendations",[]):
                        st.code(rec, language="bash") if rec.strip().startswith(
                            tuple(["top","ps","du","df","free","find","journalctl",
                                   "docker","iostat","vmstat","systemctl","cat","kill","echo"])
                        ) else st.markdown(f"- {rec}")
            elif result:
                st.error(f"Error: {result.get('error','Unknown')}")

    st.markdown("---")
    with st.expander("🔧 Diagnose custom values"):
        c1,c2,c3 = st.columns(3)
        mc = c1.slider("CPU %",0,100,50)
        mm = c2.slider("Memory %",0,100,60)
        md = c3.slider("Disk %",0,100,40)
        if st.button("Analyse"):
            manual = {"server_name":"manual","cpu_percent":mc,"memory_percent":mm,
                      "disk_percent":md,"uptime_seconds":0,"process_count":0,
                      "load_avg_1m":0,"load_avg_5m":0,"load_avg_15m":0,
                      "net_bytes_sent":0,"net_bytes_recv":0}
            with st.spinner("Analysing..."):
                r = _post("/api/ai/diagnose", {"server_name":"manual","metrics":manual})
            if r and "error" not in r:
                st.json(r)

# ── Auto-refresh ────────────────────────────────────────
if st.sidebar.checkbox("⚡ Auto-refresh", value=False):
    time.sleep(REFRESH_SEC)
    st.cache_data.clear()
    st.rerun()

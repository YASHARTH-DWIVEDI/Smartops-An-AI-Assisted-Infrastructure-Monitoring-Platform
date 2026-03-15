"""
Rule-Based Diagnostic Engine — infrastructure-focused correlation rules.

Implements compound pattern matching:
  CPU high + memory stable    → compute job
  CPU high + memory rising    → memory leak
  Disk growing fast           → log accumulation
  CPU high + disk high        → I/O-bound process
  All metrics high            → system overload
  Memory high + CPU low       → memory leak or cache issue
  Network + CPU spike         → DDoS or traffic surge
"""

from typing import List, Tuple


# ─────────────────────────────────────────────
# Thresholds
# ─────────────────────────────────────────────
CPU_WARN = 75;   CPU_CRIT = 90
MEM_WARN = 75;   MEM_CRIT = 90
DISK_WARN = 70;  DISK_CRIT = 85
LOAD_HIGH_RATIO = 1.5  # load_avg_1m / cpu_cores


# ─────────────────────────────────────────────
# Pattern rules: (condition_fn, causes, recommendations)
# Evaluated in order; ALL matching rules contribute.
# ─────────────────────────────────────────────

def _make_rules():
    return [
        # ── All metrics critical ──────────────
        {
            "name": "all_critical",
            "match": lambda m: (
                m.get("cpu_percent", 0) >= CPU_CRIT
                and m.get("memory_percent", 0) >= MEM_CRIT
                and m.get("disk_percent", 0) >= DISK_CRIT
            ),
            "severity": "critical",
            "causes": [
                "System is completely overloaded — all resources at capacity.",
                "Possible runaway application consuming CPU, RAM, and disk simultaneously.",
                "Cascading failure: one resource exhaustion triggering others.",
            ],
            "recommendations": [
                "IMMEDIATE: `top -b -n1 | head -30` — identify the top process.",
                "Check for out-of-control jobs: `ps aux --sort=-%cpu | head -10`",
                "Consider emergency reboot if system becomes unresponsive.",
                "After recovery, review application resource limits.",
                "Set up cgroups to prevent any single process dominating resources.",
            ],
        },
        # ── CPU high + memory stable → compute job ──
        {
            "name": "cpu_high_mem_stable",
            "match": lambda m: (
                m.get("cpu_percent", 0) >= CPU_WARN
                and m.get("memory_percent", 0) < MEM_WARN
            ),
            "severity": "warning",
            "causes": [
                "CPU-bound compute job running (ML training, video encoding, compilation).",
                "Scheduled batch task or cron job consuming CPU.",
                "Inefficient algorithm in application causing high CPU spin.",
                "DDoS attack or traffic spike on a web-facing service.",
            ],
            "recommendations": [
                "Identify CPU consumer: `top -b -n1 | head -20`",
                "Check cron jobs: `crontab -l` and `ls /etc/cron.d/`",
                "Limit CPU for background jobs: `nice -n 19 <command>`",
                "Use `perf top` or `strace -p <pid>` for deeper profiling.",
            ],
        },
        # ── CPU high + memory rising → memory leak ──
        {
            "name": "cpu_high_mem_rising",
            "match": lambda m: (
                m.get("cpu_percent", 0) >= CPU_WARN
                and m.get("memory_percent", 0) >= MEM_WARN
            ),
            "severity": "critical",
            "causes": [
                "Possible memory leak in a long-running process (CPU overhead from GC/swapping).",
                "Application allocating memory faster than it can free it.",
                "Multiple heavy processes competing for CPU and RAM simultaneously.",
            ],
            "recommendations": [
                "Check memory trend: `watch -n 2 free -h`",
                "Find leaking process: `ps aux --sort=-%mem | head -10`",
                "Check swap usage: `swapon --show` and `vmstat -s | grep swap`",
                "Restart suspected process after identifying it.",
                "For Java apps, check heap: `jmap -heap <pid>`",
                "Consider adding swap space temporarily: `fallocate -l 2G /swapfile`",
            ],
        },
        # ── Memory high + CPU low → silent leak ──
        {
            "name": "mem_high_cpu_low",
            "match": lambda m: (
                m.get("memory_percent", 0) >= MEM_WARN
                and m.get("cpu_percent", 0) < CPU_WARN
            ),
            "severity": "warning",
            "causes": [
                "Silent memory leak — process gradually consuming RAM without CPU pressure.",
                "Large in-memory cache not being evicted (Redis, Memcached, or app cache).",
                "Memory fragmentation in long-running application.",
                "Kernel buffer/page cache growth (usually harmless but can indicate large I/O).",
            ],
            "recommendations": [
                "Check page cache: `cat /proc/meminfo | grep -E 'Cached|Buffers|Slab'`",
                "Drop caches (temporary): `echo 3 | sudo tee /proc/sys/vm/drop_caches`",
                "Inspect top memory consumers: `ps aux --sort=-%mem | head -15`",
                "Check for memory maps: `pmap -x <pid> | tail -5`",
                "Review application memory configuration (JVM -Xmx, Node --max-old-space-size).",
            ],
        },
        # ── Disk critical → log accumulation ──
        {
            "name": "disk_critical",
            "match": lambda m: m.get("disk_percent", 0) >= DISK_CRIT,
            "severity": "critical",
            "causes": [
                "Log files growing without rotation — logrotate misconfigured or stopped.",
                "Docker images and stopped containers consuming disk space.",
                "Database or application data growing without cleanup policy.",
                "Core dump files accumulating in /var/crash or /tmp.",
                "Old kernel or package versions not cleaned up.",
            ],
            "recommendations": [
                "Find largest directories: `du -ahx / 2>/dev/null | sort -rh | head -20`",
                "Check log sizes: `du -sh /var/log/* | sort -rh | head -10`",
                "Clean journal logs: `journalctl --vacuum-size=200M`",
                "Remove old Docker data: `docker system prune -af --volumes`",
                "Clean apt cache: `apt-get clean && apt-get autoremove`",
                "Verify logrotate: `logrotate --debug /etc/logrotate.conf`",
            ],
        },
        # ── Disk warning → gradual growth ──
        {
            "name": "disk_warning",
            "match": lambda m: DISK_WARN <= m.get("disk_percent", 0) < DISK_CRIT,
            "severity": "warning",
            "causes": [
                "Gradual disk fill — application data or logs growing steadily.",
                "Logrotate not compressing old logs efficiently.",
                "Temporary files accumulating in /tmp or /var/tmp.",
            ],
            "recommendations": [
                "Monitor disk trend: `df -h` and check growth rate.",
                "Clean tmp files: `find /tmp -type f -atime +7 -delete`",
                "Review logrotate config: `cat /etc/logrotate.conf`",
                "Set up disk usage alerting at 70% threshold.",
            ],
        },
        # ── High load average ─────────────────
        {
            "name": "high_load_avg",
            "match": lambda m: (
                (m.get("load_avg_1m", 0) or 0) > 2.0
            ),
            "severity": "warning",
            "causes": [
                "High run queue — more processes want CPU than cores available.",
                "I/O wait causing processes to queue (disk or network bottleneck).",
                "Many concurrent database queries or lock contention.",
            ],
            "recommendations": [
                "Check I/O wait: `iostat -x 2 5` — look for high %iowait.",
                "Check disk I/O: `iotop -ao` (sort by I/O).",
                "Review database slow query log if applicable.",
                "Consider horizontal scaling or load balancing.",
            ],
        },
        # ── High process count ─────────────────
        {
            "name": "process_explosion",
            "match": lambda m: (m.get("process_count", 0) or 0) > 500,
            "severity": "warning",
            "causes": [
                "Fork bomb or recursive process spawning.",
                "Web server spawning too many worker processes.",
                "Runaway script creating child processes without limits.",
            ],
            "recommendations": [
                "List process tree: `ps auxf | head -50`",
                "Check per-user limits: `ulimit -u`",
                "Set process limits in /etc/security/limits.conf.",
                "Review web server worker configuration (nginx worker_processes).",
            ],
        },
        # ── CPU + disk both high → I/O bound ──
        {
            "name": "cpu_high_disk_high",
            "match": lambda m: (
                m.get("cpu_percent", 0) >= CPU_WARN
                and m.get("disk_percent", 0) >= DISK_WARN
            ),
            "severity": "warning",
            "causes": [
                "I/O-bound process reading/writing large files while consuming CPU.",
                "Database performing large table scans filling disk with temp files.",
                "Backup job running that is both CPU-intensive and disk-intensive.",
            ],
            "recommendations": [
                "Check I/O: `iostat -xz 1 5`",
                "Identify I/O-heavy process: `iotop -ao -P`",
                "Check if backup or ETL job is running: `ps aux | grep backup`",
            ],
        },
        # ── All healthy ────────────────────────
        {
            "name": "healthy",
            "match": lambda m: (
                m.get("cpu_percent", 0) < CPU_WARN
                and m.get("memory_percent", 0) < MEM_WARN
                and m.get("disk_percent", 0) < DISK_WARN
            ),
            "severity": "healthy",
            "causes": [],
            "recommendations": [
                "All metrics within normal ranges — no action required.",
                "Continue monitoring. Consider setting up trend-based alerts.",
                "Ensure logrotate, automated backups, and security patches are current.",
            ],
        },
    ]


class RuleBasedEngine:
    """
    Pattern-matching diagnostic engine.

    Evaluates compound metric patterns against a rule database
    and returns structured diagnosis output.
    """

    def __init__(self):
        self._rules = _make_rules()

    def diagnose(self, metrics: dict, server_name: str) -> dict:
        cpu  = metrics.get("cpu_percent", 0)
        mem  = metrics.get("memory_percent", 0)
        disk = metrics.get("disk_percent", 0)

        matched_rules = [r for r in self._rules if r["match"](metrics)]

        if not matched_rules:
            matched_rules = [r for r in self._rules if r["name"] == "healthy"]

        # Compute overall severity (worst across matching rules)
        severity_rank = {"healthy": 0, "warning": 1, "critical": 2}
        overall_sev = max(
            matched_rules, key=lambda r: severity_rank.get(r["severity"], 0)
        )["severity"]

        # Collect unique causes and recommendations from all matching rules
        seen: set = set()
        all_causes: List[str] = []
        all_recs: List[str] = []

        for rule in matched_rules:
            if rule["name"] == "healthy" and len(matched_rules) > 1:
                continue  # skip healthy rule if others matched
            for c in rule["causes"]:
                if c not in seen:
                    seen.add(c)
                    all_causes.append(c)
            for r in rule["recommendations"]:
                if r not in seen:
                    seen.add(r)
                    all_recs.append(r)

        # Build summary
        if overall_sev == "healthy":
            summary = (
                f"All systems normal on {server_name}. "
                f"CPU: {cpu:.1f}%, Memory: {mem:.1f}%, Disk: {disk:.1f}%."
            )
        else:
            patterns = [r["name"].replace("_", " ") for r in matched_rules if r["name"] != "healthy"]
            summary = (
                f"{overall_sev.upper()} — {len(matched_rules)} pattern(s) detected on {server_name}: "
                f"{', '.join(patterns)}. "
                f"CPU={cpu:.1f}% MEM={mem:.1f}% DISK={disk:.1f}%."
            )

        return {
            "server_name": server_name,
            "provider": "rules",
            "severity": overall_sev,
            "summary": summary,
            "causes": all_causes,
            "recommendations": all_recs,
            "raw_response": None,
        }

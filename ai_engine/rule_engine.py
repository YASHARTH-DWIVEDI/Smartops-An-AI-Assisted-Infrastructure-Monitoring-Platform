"""
ai_engine/rule_engine.py
─────────────────────────
Rule-based diagnostic fallback.
Used when no AI API key is configured, or as a safety net if the
AI provider call fails.

Design
------
Each rule checks a condition on the metric snapshot and appends
a finding + suggestions.  The result is deterministic and cheap.
"""

from __future__ import annotations

from typing import Any


# ── Rule definitions ──────────────────────────────────────────────────────────

def _high_cpu(m: dict) -> tuple[str, list[str]] | None:
    v = m.get("cpu_percent", 0)
    if v > 90:
        return (
            f"Critical CPU usage ({v:.1f}%) detected.",
            [
                "Identify the top CPU-consuming processes with `top` or `htop`.",
                "Check for run-away cron jobs or batch processes.",
                "Consider scaling horizontally or vertically if this is sustained.",
                "Review application profiling — look for infinite loops or tight polling.",
            ],
        )
    if v > 75:
        return (
            f"Elevated CPU usage ({v:.1f}%) — approaching critical.",
            [
                "Monitor trend over the next 10–15 minutes.",
                "Check if a scheduled job is running (`crontab -l`).",
            ],
        )
    return None


def _high_memory(m: dict) -> tuple[str, list[str]] | None:
    v = m.get("memory_percent", 0)
    if v > 90:
        return (
            f"Critical memory usage ({v:.1f}%).",
            [
                "Check for memory leaks: `ps aux --sort=-%mem | head -10`.",
                "Review application heap sizes and JVM/Node/Python memory settings.",
                "Consider restarting the offending service if safe to do so.",
                "Add swap space as a temporary measure: `fallocate -l 2G /swapfile`.",
            ],
        )
    if v > 80:
        return (
            f"High memory usage ({v:.1f}%).",
            [
                "Monitor memory trend — may indicate a slow leak.",
                "Check cache sizing; some apps over-allocate page cache.",
            ],
        )
    return None


def _high_disk(m: dict) -> tuple[str, list[str]] | None:
    v = m.get("disk_percent", 0)
    if v > 95:
        return (
            f"Disk critically full ({v:.1f}%) — risk of data loss / service crash.",
            [
                "Immediately clear old logs: `journalctl --vacuum-size=500M`.",
                "Remove stale Docker images: `docker system prune -a`.",
                "Find large files: `du -sh /* | sort -rh | head -20`.",
                "Move or archive old data to object storage.",
            ],
        )
    if v > 85:
        return (
            f"Disk usage high ({v:.1f}%).",
            [
                "Schedule a log rotation review.",
                "Audit `/var/log` and application temp directories.",
                "Consider adding disk capacity or moving data.",
            ],
        )
    return None


def _low_uptime(m: dict) -> tuple[str, list[str]] | None:
    v = m.get("uptime_seconds", 9999)
    if v < 300:  # less than 5 minutes
        return (
            f"Server was recently rebooted (uptime: {v:.0f}s).",
            [
                "Check system logs for crash evidence: `journalctl -p err -b`.",
                "Verify all required services have restarted: `systemctl --failed`.",
                "Check for OOM-killer events: `dmesg | grep -i oom`.",
            ],
        )
    return None


def _high_process_count(m: dict) -> tuple[str, list[str]] | None:
    v = m.get("process_count", 0)
    if v > 500:
        return (
            f"Unusually high process count ({v}).",
            [
                "Check for fork-bombs or runaway spawning: `ps aux | wc -l`.",
                "Review ulimits: `ulimit -a`.",
                "Look for zombie processes: `ps aux | grep 'Z'`.",
            ],
        )
    return None


_ALL_RULES = [
    _high_cpu,
    _high_memory,
    _high_disk,
    _low_uptime,
    _high_process_count,
]


# ── Public API ────────────────────────────────────────────────────────────────

def analyze(server_name: str, metrics: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run all rules against the most recent metric snapshot (metrics[0]).
    Returns a dict with analysis text and a flat list of suggestions.
    """
    if not metrics:
        return {
            "provider": "rule_based",
            "analysis": "No metrics available to analyse.",
            "suggestions": ["Ensure the monitoring agent is running and connected."],
        }

    latest = metrics[0]

    findings: list[str] = []
    suggestions: list[str] = []

    for rule in _ALL_RULES:
        result = rule(latest)
        if result:
            finding, sug = result
            findings.append(finding)
            suggestions.extend(sug)

    if findings:
        analysis = (
            f"SmartOps rule-based analysis for **{server_name}**:\n\n"
            + "\n".join(f"• {f}" for f in findings)
        )
    else:
        analysis = (
            f"All metrics for **{server_name}** are within normal ranges. "
            f"CPU {latest.get('cpu_percent', 0):.1f}%, "
            f"Memory {latest.get('memory_percent', 0):.1f}%, "
            f"Disk {latest.get('disk_percent', 0):.1f}%."
        )
        suggestions = [
            "Continue routine monitoring.",
            "Ensure backups are up-to-date.",
            "Review capacity planning for the next quarter.",
        ]

    return {
        "provider": "rule_based",
        "analysis": analysis,
        "suggestions": suggestions,
    }

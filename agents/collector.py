"""
agent/collector.py
───────────────────
Collects system metrics using psutil.
Returns a clean dict ready to POST to the API.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import psutil
from loguru import logger


def collect() -> dict[str, Any]:
    """
    Gather a full system snapshot.

    Returns
    -------
    dict matching MetricPayload schema expected by the API.
    """
    ts = datetime.now(timezone.utc)

    # ── CPU ──────────────────────────────────────────────────────────────
    # interval=1 → blocks for 1 second to get an accurate reading
    cpu_percent = psutil.cpu_percent(interval=1)

    # ── Memory ───────────────────────────────────────────────────────────
    mem = psutil.virtual_memory()
    memory_percent = mem.percent
    memory_used_mb = mem.used / (1024 ** 2)
    memory_total_mb = mem.total / (1024 ** 2)

    # ── Disk (root partition) ─────────────────────────────────────────────
    disk = psutil.disk_usage("/")
    disk_percent = disk.percent
    disk_used_gb = disk.used / (1024 ** 3)
    disk_total_gb = disk.total / (1024 ** 3)

    # ── Network (cumulative counters since boot) ───────────────────────────
    net = psutil.net_io_counters()
    net_bytes_sent = float(net.bytes_sent)
    net_bytes_recv = float(net.bytes_recv)

    # ── Uptime ────────────────────────────────────────────────────────────
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time

    # ── Processes ─────────────────────────────────────────────────────────
    process_count = len(psutil.pids())

    snapshot = {
        "timestamp": ts.isoformat(),
        "cpu_percent": cpu_percent,
        "memory_percent": memory_percent,
        "memory_used_mb": round(memory_used_mb, 2),
        "memory_total_mb": round(memory_total_mb, 2),
        "disk_percent": disk_percent,
        "disk_used_gb": round(disk_used_gb, 3),
        "disk_total_gb": round(disk_total_gb, 3),
        "net_bytes_sent": net_bytes_sent,
        "net_bytes_recv": net_bytes_recv,
        "uptime_seconds": round(uptime_seconds, 1),
        "process_count": process_count,
    }

    logger.debug(
        "Collected | cpu={cpu_percent:.1f}% mem={memory_percent:.1f}% "
        "disk={disk_percent:.1f}% procs={process_count}",
        **snapshot,
    )
    return snapshot


def top_processes(n: int = 5) -> list[dict[str, Any]]:
    """Return the top-N CPU-consuming processes (useful for diagnostics)."""
    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p.get("cpu_percent") or 0, reverse=True)
    return procs[:n]

"""
Metric Collector — gathers system metrics using psutil.

Collected metrics:
  - CPU usage (%)
  - Memory usage (%)
  - Disk usage (%) — root partition
  - Network I/O (bytes sent/received since last call)
  - System uptime (seconds)
  - Top processes by CPU
"""

import os
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import psutil

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.logging_config import get_logger

logger = get_logger("agent.collector")


@dataclass
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    memory_percent: float
    status: str


@dataclass
class SystemMetrics:
    """All metrics captured in a single collection cycle."""
    server_name: str
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float
    net_bytes_sent: int
    net_bytes_recv: int
    uptime_seconds: float
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    process_count: int
    top_processes: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


class MetricCollector:
    """
    Collects system metrics using psutil.

    Network deltas are calculated between successive calls,
    so the first call returns 0 for net_bytes_sent/recv.
    """

    def __init__(self, server_name: str):
        self.server_name = server_name
        self._last_net = psutil.net_io_counters()
        self._last_net_time = time.monotonic()
        logger.info(f"MetricCollector initialised for server '{server_name}'")

    def collect(self) -> SystemMetrics:
        """Collect all metrics and return a SystemMetrics dataclass."""
        try:
            cpu = self._collect_cpu()
            memory = self._collect_memory()
            disk = self._collect_disk()
            net = self._collect_network()
            uptime = self._collect_uptime()
            load = self._collect_load_avg()
            processes = self._collect_processes()

            metrics = SystemMetrics(
                server_name=self.server_name,
                cpu_percent=cpu,
                memory_percent=memory["percent"],
                memory_used_mb=memory["used_mb"],
                memory_total_mb=memory["total_mb"],
                disk_percent=disk["percent"],
                disk_used_gb=disk["used_gb"],
                disk_total_gb=disk["total_gb"],
                net_bytes_sent=net["sent"],
                net_bytes_recv=net["recv"],
                uptime_seconds=uptime,
                load_avg_1m=load[0],
                load_avg_5m=load[1],
                load_avg_15m=load[2],
                process_count=len(psutil.pids()),
                top_processes=processes,
            )

            logger.debug(
                f"Collected: CPU={cpu:.1f}% MEM={memory['percent']:.1f}% "
                f"DISK={disk['percent']:.1f}%"
            )
            return metrics

        except Exception as e:
            logger.error(f"Metric collection error: {e}", exc_info=True)
            raise

    # ──────────────────────────────────────────
    # Individual collectors
    # ──────────────────────────────────────────

    def _collect_cpu(self) -> float:
        """CPU usage percent (non-blocking, 1-second interval)."""
        try:
            return psutil.cpu_percent(interval=1)
        except Exception as e:
            logger.warning(f"CPU collection failed: {e}")
            return 0.0

    def _collect_memory(self) -> dict:
        try:
            mem = psutil.virtual_memory()
            return {
                "percent": mem.percent,
                "used_mb": round(mem.used / 1024 / 1024, 2),
                "total_mb": round(mem.total / 1024 / 1024, 2),
            }
        except Exception as e:
            logger.warning(f"Memory collection failed: {e}")
            return {"percent": 0.0, "used_mb": 0.0, "total_mb": 0.0}

    def _collect_disk(self, path: str = "/") -> dict:
        try:
            disk = psutil.disk_usage(path)
            return {
                "percent": disk.percent,
                "used_gb": round(disk.used / 1024 ** 3, 2),
                "total_gb": round(disk.total / 1024 ** 3, 2),
            }
        except Exception as e:
            logger.warning(f"Disk collection failed: {e}")
            return {"percent": 0.0, "used_gb": 0.0, "total_gb": 0.0}

    def _collect_network(self) -> dict:
        """Return bytes sent/received SINCE last call (delta)."""
        try:
            now = time.monotonic()
            current = psutil.net_io_counters()
            delta_sent = max(0, current.bytes_sent - self._last_net.bytes_sent)
            delta_recv = max(0, current.bytes_recv - self._last_net.bytes_recv)
            self._last_net = current
            self._last_net_time = now
            return {"sent": delta_sent, "recv": delta_recv}
        except Exception as e:
            logger.warning(f"Network collection failed: {e}")
            return {"sent": 0, "recv": 0}

    def _collect_uptime(self) -> float:
        try:
            return time.time() - psutil.boot_time()
        except Exception as e:
            logger.warning(f"Uptime collection failed: {e}")
            return 0.0

    def _collect_load_avg(self) -> tuple:
        try:
            if hasattr(os, "getloadavg"):
                return os.getloadavg()
            return (0.0, 0.0, 0.0)
        except Exception:
            return (0.0, 0.0, 0.0)

    def _collect_processes(self, top_n: int = 5) -> list:
        """Return top N processes by CPU usage."""
        try:
            procs = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
                try:
                    info = proc.info
                    procs.append({
                        "pid": info["pid"],
                        "name": info["name"] or "unknown",
                        "cpu_percent": round(info["cpu_percent"] or 0, 2),
                        "memory_percent": round(info["memory_percent"] or 0, 2),
                        "status": info["status"] or "unknown",
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by CPU descending
            procs.sort(key=lambda x: x["cpu_percent"], reverse=True)
            return procs[:top_n]

        except Exception as e:
            logger.warning(f"Process collection failed: {e}")
            return []

"""
Log Collector — gathers recent log lines from system log sources.

Sources (collected if path exists + readable):
  - /var/log/syslog          (general system log)
  - /var/log/auth.log        (authentication events)
  - /var/log/nginx/access.log
  - /var/log/nginx/error.log
  - Docker container logs    (via `docker logs --tail N`)
  - journald                 (via `journalctl -n N`)

Only the most recent N lines per source are collected to keep
payload size small. Lines are deduped by content hash.
"""

import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.logging_config import get_logger

logger = get_logger("agent.log_collector")

# ── Configuration ─────────────────────────────

DEFAULT_TAIL_LINES = int(os.getenv("LOG_TAIL_LINES", "50"))

LOG_SOURCES = [
    {"name": "syslog",      "path": "/var/log/syslog"},
    {"name": "auth",        "path": "/var/log/auth.log"},
    {"name": "kern",        "path": "/var/log/kern.log"},
    {"name": "nginx_access","path": "/var/log/nginx/access.log"},
    {"name": "nginx_error", "path": "/var/log/nginx/error.log"},
    {"name": "apache2",     "path": "/var/log/apache2/error.log"},
    {"name": "dpkg",        "path": "/var/log/dpkg.log"},
]


@dataclass
class LogEntry:
    """A single collected log line."""
    source: str           # syslog | nginx_access | docker:<name> | journald
    level: str            # info | warn | error | unknown
    message: str
    timestamp: str        # raw timestamp string as found in the log
    line_hash: str        # sha256[:12] for deduplication


@dataclass
class LogBatch:
    """All log entries collected in one cycle."""
    server_name: str
    collected_at: str
    entries: List[dict] = field(default_factory=list)
    sources_read: List[str] = field(default_factory=list)
    sources_failed: List[str] = field(default_factory=list)
    total_lines: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class LogCollector:
    """
    Collects recent log lines from multiple sources on this host.

    Designed to be called periodically (e.g., every 30s) alongside
    metric collection. Sends only new lines since last collection
    via deduplication by line hash.
    """

    def __init__(
        self,
        server_name: str,
        tail_lines: int = DEFAULT_TAIL_LINES,
        collect_docker: bool = True,
        collect_journald: bool = True,
    ):
        self.server_name = server_name
        self.tail_lines = tail_lines
        self.collect_docker = collect_docker
        self.collect_journald = collect_journald
        self._seen_hashes: set = set()
        logger.info(f"LogCollector initialised for '{server_name}' (tail={tail_lines})")

    def collect(self) -> LogBatch:
        """Collect log lines from all available sources."""
        batch = LogBatch(
            server_name=self.server_name,
            collected_at=datetime.utcnow().isoformat(),
        )

        # ── File-based sources ────────────────────
        for source_def in LOG_SOURCES:
            name = source_def["name"]
            path = source_def["path"]
            try:
                entries = self._read_file_tail(name, path)
                if entries:
                    new_entries = self._deduplicate(entries)
                    batch.entries.extend([e.__dict__ for e in new_entries])
                    batch.sources_read.append(name)
            except PermissionError:
                logger.debug(f"No read permission for {path}")
                batch.sources_failed.append(name)
            except Exception as e:
                logger.debug(f"Log source {name} unavailable: {e}")

        # ── journald ─────────────────────────────
        if self.collect_journald:
            try:
                entries = self._read_journald()
                if entries:
                    new_entries = self._deduplicate(entries)
                    batch.entries.extend([e.__dict__ for e in new_entries])
                    batch.sources_read.append("journald")
            except Exception as e:
                logger.debug(f"journald unavailable: {e}")

        # ── Docker container logs ─────────────────
        if self.collect_docker:
            try:
                docker_entries = self._read_docker_logs()
                if docker_entries:
                    new_entries = self._deduplicate(docker_entries)
                    batch.entries.extend([e.__dict__ for e in new_entries])
                    if docker_entries:
                        batch.sources_read.append("docker")
            except Exception as e:
                logger.debug(f"Docker logs unavailable: {e}")

        batch.total_lines = len(batch.entries)
        logger.debug(
            f"Log collection: {batch.total_lines} lines from "
            f"{len(batch.sources_read)} sources"
        )
        return batch

    # ──────────────────────────────────────────
    # File-based log reading
    # ──────────────────────────────────────────

    def _read_file_tail(self, source_name: str, path: str) -> List[LogEntry]:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return []

        # Use tail for efficiency on large files
        result = subprocess.run(
            ["tail", f"-n{self.tail_lines}", path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []

        entries = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            entries.append(LogEntry(
                source=source_name,
                level=_detect_level(line),
                message=line[:1000],  # truncate very long lines
                timestamp=_extract_timestamp(line),
                line_hash=_hash_line(line),
            ))
        return entries

    # ──────────────────────────────────────────
    # journald
    # ──────────────────────────────────────────

    def _read_journald(self) -> List[LogEntry]:
        """Read recent entries from systemd journal."""
        result = subprocess.run(
            [
                "journalctl",
                f"-n{self.tail_lines}",
                "--no-pager",
                "--output=short-iso",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []

        entries = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            entries.append(LogEntry(
                source="journald",
                level=_detect_level(line),
                message=line[:1000],
                timestamp=_extract_timestamp(line),
                line_hash=_hash_line(line),
            ))
        return entries

    # ──────────────────────────────────────────
    # Docker logs
    # ──────────────────────────────────────────

    def _read_docker_logs(self) -> List[LogEntry]:
        """Collect logs from all running Docker containers."""
        # Get running container IDs and names
        ps_result = subprocess.run(
            ["docker", "ps", "--format", "{{.ID}} {{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if ps_result.returncode != 0:
            return []

        all_entries = []
        for line in ps_result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                continue
            container_id, container_name = parts[0], parts[1]

            try:
                logs_result = subprocess.run(
                    ["docker", "logs", "--tail", str(self.tail_lines // 2), container_id],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                output = logs_result.stdout + logs_result.stderr
                for log_line in output.splitlines():
                    log_line = log_line.strip()
                    if not log_line:
                        continue
                    all_entries.append(LogEntry(
                        source=f"docker:{container_name}",
                        level=_detect_level(log_line),
                        message=log_line[:1000],
                        timestamp=_extract_timestamp(log_line),
                        line_hash=_hash_line(log_line),
                    ))
            except Exception as e:
                logger.debug(f"Failed to read logs for {container_name}: {e}")

        return all_entries

    # ──────────────────────────────────────────
    # Deduplication
    # ──────────────────────────────────────────

    def _deduplicate(self, entries: List[LogEntry]) -> List[LogEntry]:
        """Return only entries not seen in previous collections."""
        new_entries = []
        for entry in entries:
            if entry.line_hash not in self._seen_hashes:
                self._seen_hashes.add(entry.line_hash)
                new_entries.append(entry)

        # Keep seen set bounded to avoid memory growth
        if len(self._seen_hashes) > 50_000:
            self._seen_hashes = set(list(self._seen_hashes)[-25_000:])

        return new_entries


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _hash_line(line: str) -> str:
    """Short hash for deduplication."""
    return hashlib.sha256(line.encode()).hexdigest()[:16]


def _detect_level(line: str) -> str:
    """Classify a log line severity from keywords."""
    lower = line.lower()
    if any(w in lower for w in ("error", "err", "crit", "critical", "fatal", "panic", "emerg")):
        return "error"
    if any(w in lower for w in ("warn", "warning")):
        return "warn"
    if any(w in lower for w in ("debug", "trace", "verbose")):
        return "debug"
    return "info"


def _extract_timestamp(line: str) -> str:
    """Try to extract the timestamp prefix from a log line."""
    # Common formats: "Mar 15 10:22:34", "2024-03-15T10:22:34", "2024/03/15 10:22:34"
    parts = line.split()
    if len(parts) >= 3:
        # syslog style: "Mar 15 10:22:34 ..."
        candidate = " ".join(parts[:3])
        if len(candidate) <= 20:
            return candidate
    return ""

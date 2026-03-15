"""
agent/agent.py
───────────────
Main monitoring agent entry point.

Run with:
    python -m agent.agent

The agent runs indefinitely, collecting system metrics every
AGENT_INTERVAL seconds and shipping them to the SmartOps API.
It never crashes — all errors are caught and logged.
"""

from __future__ import annotations

import signal
import socket
import sys
import time

from loguru import logger

from agent.collector import collect
from agent.sender import send
from config.settings import get_settings

settings = get_settings()

# ── Logging setup ─────────────────────────────────────────────────────────────

logger.remove()
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<cyan>{time:HH:mm:ss}</cyan> | <level>{level:<8}</level> | AGENT | {message}",
    colorize=True,
)
logger.add(
    settings.log_file,
    level=settings.log_level,
    rotation="5 MB",
    retention="7 days",
    compression="gz",
)

# ── Graceful shutdown ──────────────────────────────────────────────────────────

_running = True


def _handle_signal(sig: int, _frame) -> None:  # type: ignore[type-arg]
    global _running
    logger.info("Signal {} received — shutting down agent gracefully.", sig)
    _running = False


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


# ── Agent loop ────────────────────────────────────────────────────────────────

def run() -> None:
    server_name = settings.server_name or socket.gethostname()
    interval = settings.agent_interval

    logger.info("=" * 50)
    logger.info("SmartOps Monitoring Agent")
    logger.info("  Server name : {}", server_name)
    logger.info("  API URL     : {}", settings.agent_api_url)
    logger.info("  Interval    : {}s", interval)
    logger.info("  Log level   : {}", settings.log_level)
    logger.info("=" * 50)

    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 10

    while _running:
        loop_start = time.monotonic()

        try:
            # 1. Collect metrics from this machine
            snapshot = collect()
            snapshot["server_name"] = server_name

            # 2. Ship to API (internally retries on transient errors)
            success = send(snapshot)

            if success:
                consecutive_failures = 0
                logger.info(
                    "✓ Metric shipped | cpu={:.1f}% mem={:.1f}% disk={:.1f}%",
                    snapshot["cpu_percent"],
                    snapshot["memory_percent"],
                    snapshot["disk_percent"],
                )
            else:
                consecutive_failures += 1
                logger.warning(
                    "✗ Failed to ship metric ({}/{} consecutive failures)",
                    consecutive_failures,
                    MAX_CONSECUTIVE_FAILURES,
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.critical(
                        "Too many consecutive failures — check API connectivity. "
                        "Agent continues running."
                    )
                    consecutive_failures = 0  # reset so we don't spam

        except Exception as exc:
            logger.exception("Unexpected error in agent loop: {}", exc)

        # Sleep for the remainder of the interval (account for collection time)
        elapsed = time.monotonic() - loop_start
        sleep_time = max(0.0, interval - elapsed)
        if _running:
            time.sleep(sleep_time)

    logger.info("Agent stopped.")


if __name__ == "__main__":
    run()

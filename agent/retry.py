"""
Retry Module — exponential backoff with local disk buffering.

When the SmartOps API is unreachable the agent must not lose data.
This module provides:

  RetryBuffer   — persists unsent payloads to a local JSON file
                  so data survives agent restarts.

  with_retry()  — decorator / context manager for exponential backoff
                  with jitter on any callable.

Buffer file format: newline-delimited JSON (ndjson)
  {"type": "metrics", "payload": {...}, "queued_at": "2024-..."}
  {"type": "logs",    "payload": {...}, "queued_at": "2024-..."}
"""

import json
import os
import random
import sys
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.logging_config import get_logger

logger = get_logger("agent.retry")

# ── Default configuration ─────────────────────

DEFAULT_BUFFER_PATH = os.getenv("AGENT_BUFFER_FILE", "/tmp/smartops_agent_buffer.ndjson")
DEFAULT_MAX_ENTRIES = int(os.getenv("AGENT_BUFFER_MAX", "500"))
DEFAULT_MAX_ATTEMPTS = int(os.getenv("AGENT_RETRY_ATTEMPTS", "3"))
DEFAULT_BASE_DELAY = float(os.getenv("AGENT_RETRY_DELAY", "2.0"))
DEFAULT_MAX_DELAY = float(os.getenv("AGENT_RETRY_MAX_DELAY", "60.0"))


# ── RetryBuffer ───────────────────────────────

class RetryBuffer:
    """
    Persistent local buffer for unsent payloads.

    Writes to a newline-delimited JSON file so data survives
    agent restarts or crashes.

    Thread safety: Not thread-safe — designed for single-threaded agent.
    """

    def __init__(
        self,
        buffer_path: str = DEFAULT_BUFFER_PATH,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ):
        self.buffer_path = Path(buffer_path)
        self.max_entries = max_entries
        self._in_memory: List[dict] = []

        # Load any existing buffered data from previous run
        self._load_from_disk()
        if self._in_memory:
            logger.info(
                f"RetryBuffer: loaded {len(self._in_memory)} buffered entries from {buffer_path}"
            )

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def push(self, payload_type: str, payload: dict) -> None:
        """Add a payload to the buffer."""
        if len(self._in_memory) >= self.max_entries:
            # Evict oldest entry to make room
            evicted = self._in_memory.pop(0)
            logger.warning(
                f"Buffer full ({self.max_entries}). Evicting oldest entry "
                f"(type={evicted.get('type')} queued_at={evicted.get('queued_at')})"
            )

        entry = {
            "type": payload_type,
            "payload": payload,
            "queued_at": datetime.utcnow().isoformat(),
            "attempts": 0,
        }
        self._in_memory.append(entry)
        self._save_to_disk()
        logger.debug(f"Buffered {payload_type} payload. Buffer size: {len(self._in_memory)}")

    def peek_all(self) -> List[dict]:
        """Return all buffered entries without removing them."""
        return list(self._in_memory)

    def flush_sent(self, count: int) -> None:
        """Remove the first `count` entries after successful send."""
        if count > 0:
            self._in_memory = self._in_memory[count:]
            self._save_to_disk()
            logger.info(f"Flushed {count} buffered entries. Remaining: {len(self._in_memory)}")

    def increment_attempts(self, index: int) -> None:
        """Track send attempts per entry."""
        if 0 <= index < len(self._in_memory):
            self._in_memory[index]["attempts"] = self._in_memory[index].get("attempts", 0) + 1

    def drain(self, sender_func: Callable[[str, dict], bool]) -> tuple[int, int]:
        """
        Attempt to send all buffered entries.

        Args:
            sender_func: Callable(type, payload) → True on success.

        Returns:
            (sent_count, failed_count)
        """
        if not self._in_memory:
            return 0, 0

        sent = 0
        failed = 0
        still_buffered = []

        for entry in self._in_memory:
            try:
                success = sender_func(entry["type"], entry["payload"])
                if success:
                    sent += 1
                else:
                    failed += 1
                    still_buffered.append(entry)
            except Exception as e:
                failed += 1
                still_buffered.append(entry)
                logger.debug(f"Drain send failed: {e}")

        self._in_memory = still_buffered
        self._save_to_disk()

        if sent:
            logger.info(f"Drained buffer: {sent} sent, {failed} failed. Remaining: {len(self._in_memory)}")

        return sent, failed

    @property
    def size(self) -> int:
        return len(self._in_memory)

    @property
    def is_empty(self) -> bool:
        return len(self._in_memory) == 0

    # ──────────────────────────────────────────
    # Disk persistence
    # ──────────────────────────────────────────

    def _save_to_disk(self) -> None:
        try:
            self.buffer_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.buffer_path, "w", encoding="utf-8") as f:
                for entry in self._in_memory:
                    f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to persist buffer to {self.buffer_path}: {e}")

    def _load_from_disk(self) -> None:
        if not self.buffer_path.exists():
            return
        try:
            with open(self.buffer_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            self._in_memory.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass  # Skip malformed lines
        except Exception as e:
            logger.error(f"Failed to load buffer from {self.buffer_path}: {e}")

    def clear(self) -> None:
        """Clear all buffered entries (use after successful drain)."""
        self._in_memory = []
        try:
            self.buffer_path.unlink(missing_ok=True)
        except Exception:
            pass


# ── Retry decorator ───────────────────────────

def with_retry(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
):
    """
    Decorator factory: retry a function with exponential backoff + jitter.

    Usage:
        @with_retry(max_attempts=3, base_delay=2.0)
        def send_data(payload):
            ...

        # Or as a context-free function:
        result = retry_call(my_func, args=[payload], max_attempts=3)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__}: all {max_attempts} attempts failed. "
                            f"Last error: {exc}"
                        )
                        raise

                    delay = _backoff_delay(attempt, base_delay, max_delay)
                    logger.warning(
                        f"{func.__name__}: attempt {attempt}/{max_attempts} failed "
                        f"({exc}). Retrying in {delay:.1f}s..."
                    )
                    if on_retry:
                        on_retry(attempt, exc)
                    time.sleep(delay)

            raise last_exc  # unreachable but satisfies type checker
        return wrapper
    return decorator


def retry_call(
    func: Callable,
    args: list = None,
    kwargs: dict = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
) -> Any:
    """
    Call func with retry logic without using the decorator.

    Returns result on success, raises last exception after all attempts fail.
    """
    args = args or []
    kwargs = kwargs or {}
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_attempts:
                raise
            delay = _backoff_delay(attempt, base_delay, max_delay)
            logger.debug(f"retry_call attempt {attempt}/{max_attempts} failed ({exc}). Waiting {delay:.1f}s")
            time.sleep(delay)

    raise last_exc


def _backoff_delay(attempt: int, base: float, maximum: float) -> float:
    """Exponential backoff with ±20% jitter: base * 2^(attempt-1) ± jitter."""
    delay = min(base * (2 ** (attempt - 1)), maximum)
    jitter = delay * 0.2 * (random.random() * 2 - 1)  # ±20%
    return max(0.1, delay + jitter)

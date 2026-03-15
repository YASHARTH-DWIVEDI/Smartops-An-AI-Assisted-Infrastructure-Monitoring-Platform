"""
Metric Sender — sends metrics, logs, and registration payloads to the API.

Features:
  - API key authentication (Authorization: Bearer <token>)
  - Separate send_metrics(), send_logs(), register_server() methods
  - Exponential backoff retry via tenacity
  - Offline in-memory queue
"""

import os
import sys
from collections import deque
from typing import Optional

import httpx
from tenacity import (
    retry, retry_if_exception_type, stop_after_attempt,
    wait_exponential, RetryError,
)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from shared.logging_config import get_logger

logger = get_logger("agent.sender")


class MetricSender:
    def __init__(self, api_url: str, timeout: int = 10, retry_attempts: int = 3,
                 retry_delay: int = 5, offline_queue_size: int = 100, api_key: str = ""):
        self.base_url = api_url.rstrip("/")
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.api_key = api_key
        self._queue: deque = deque(maxlen=offline_queue_size)

        headers = {"Content-Type": "application/json", "User-Agent": "SmartOps-Agent/1.1"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.Client(timeout=httpx.Timeout(timeout), headers=headers)
        logger.info(f"MetricSender → {self.base_url} | auth={'yes' if api_key else 'no'}")

    def send_metrics(self, payload: dict) -> bool:
        return self._post(f"{self.base_url}/api/metrics", payload)

    def send_logs(self, payload: dict) -> bool:
        return self._post(f"{self.base_url}/api/logs", payload)

    def register_server(self, registration: dict) -> Optional[str]:
        """Register server. Returns server_id on success, None on failure."""
        try:
            resp = self._client.post(f"{self.base_url}/api/servers/register", json=registration)
            if resp.status_code in (200, 201):
                data = resp.json()
                return data.get("server_id") or data.get("id")
            logger.warning(f"Registration returned {resp.status_code}: {resp.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Registration request failed: {e}")
            return None

    def _post(self, url: str, payload: dict) -> bool:
        try:
            self._post_with_retry(url, payload)
            return True
        except (RetryError, Exception) as e:
            logger.error(f"Send failed after retries: {e}")
            return False

    def _post_with_retry(self, url: str, payload: dict) -> None:
        @retry(
            retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=1, min=self.retry_delay, max=30),
        )
        def _do():
            resp = self._client.post(url, json=payload)
            if resp.status_code not in (200, 201):
                raise httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}", request=resp.request, response=resp
                )
        _do()

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    def close(self):
        self._client.close()

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

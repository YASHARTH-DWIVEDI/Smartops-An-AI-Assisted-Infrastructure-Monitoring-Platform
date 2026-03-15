"""
agent/sender.py
────────────────
HTTP sender that POSTs metric payloads to the SmartOps API.

Features
--------
- Exponential back-off retry via tenacity (up to 5 attempts)
- Configurable timeout
- Clear error logging (never raises — agent must keep running)
"""

from __future__ import annotations

import json
from typing import Any

import requests
from loguru import logger
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config.settings import get_settings

settings = get_settings()

_ENDPOINT = f"{settings.agent_api_url.rstrip('/')}/api/v1/metrics/"
_TIMEOUT = 10  # seconds


def _before_retry(retry_state) -> None:  # type: ignore[type-arg]
    logger.warning(
        "Retry attempt {} for metric POST (error: {})",
        retry_state.attempt_number,
        retry_state.outcome.exception(),
    )


@retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    before_sleep=_before_retry,
    reraise=False,
)
def _post_with_retry(payload: dict[str, Any]) -> requests.Response:
    return requests.post(_ENDPOINT, json=payload, timeout=_TIMEOUT)


def send(payload: dict[str, Any]) -> bool:
    """
    POST a metric payload to the backend API.

    Returns True on success, False on any failure.
    Never raises — the agent loop must remain alive.
    """
    try:
        response = _post_with_retry(payload)
        if response.status_code == 201:
            logger.debug("Metric sent successfully (id={})", response.json().get("id"))
            return True
        else:
            logger.error(
                "API rejected metric | status={} body={}",
                response.status_code,
                response.text[:200],
            )
            return False
    except RetryError as exc:
        logger.error(
            "All retry attempts exhausted — could not reach API at {}. Error: {}",
            _ENDPOINT,
            exc,
        )
        return False
    except Exception as exc:
        logger.exception("Unexpected error while sending metric: {}", exc)
        return False

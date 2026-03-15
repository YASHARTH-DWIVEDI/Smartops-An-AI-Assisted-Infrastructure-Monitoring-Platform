"""
api/middleware/logging_middleware.py
─────────────────────────────────────
ASGI middleware that logs every request with timing information.
"""

from __future__ import annotations

import time
import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs:
      → incoming request (method, path, client IP)
      ← response (status code, latency ms)
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        logger.info(
            "→ {} {} | client={} id={}",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown",
            request_id,
        )

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled exception in request id={}: {}", request_id, exc)
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "← {} {} | status={} latency={:.1f}ms id={}",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )
        return response

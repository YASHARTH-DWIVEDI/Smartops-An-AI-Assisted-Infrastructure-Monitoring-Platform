"""
api/main.py
────────────
FastAPI application factory.

Start with:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from api.middleware.logging_middleware import LoggingMiddleware
from api.routers import alerts, diagnose, metrics, servers
from config.settings import get_settings
from database.session import create_tables, health_check

settings = get_settings()

# ── Logging setup ─────────────────────────────────────────────────────────────

logger.remove()  # remove default handler
logger.add(
    sys.stderr,
    level=settings.log_level,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
    colorize=True,
)
logger.add(
    settings.log_file,
    level=settings.log_level,
    rotation="10 MB",
    retention="7 days",
    compression="gz",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}",
)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Run startup tasks then yield; cleanup runs on shutdown."""
    logger.info("SmartOps API starting up...")
    logger.info("Database URL: {}", settings.database_url.split("@")[-1])  # hide creds

    # Ensure all tables exist (idempotent)
    create_tables()
    logger.info("Database tables verified ✓")

    yield  # ← application runs here

    logger.info("SmartOps API shutting down — goodbye.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SmartOps Monitoring API",
    description=(
        "Central API for the SmartOps AI-Assisted Infrastructure Monitoring Platform. "
        "Receives metrics from agents, stores them, surfaces alerts, and runs AI diagnostics."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LoggingMiddleware)

# ── Routers ───────────────────────────────────────────────────────────────────

API_PREFIX = "/api/v1"

app.include_router(metrics.router, prefix=API_PREFIX)
app.include_router(servers.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(diagnose.router, prefix=API_PREFIX)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["system"], summary="API health check")
def health() -> JSONResponse:
    db_ok = health_check()
    payload = {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    code = 200 if db_ok else 503
    return JSONResponse(content=payload, status_code=code)


@app.get("/", tags=["system"], include_in_schema=False)
def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": "SmartOps Monitoring API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }
    )

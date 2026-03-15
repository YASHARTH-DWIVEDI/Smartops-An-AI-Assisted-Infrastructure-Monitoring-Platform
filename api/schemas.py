"""
api/schemas.py
──────────────
Pydantic v2 schemas used for request validation and response serialization.
Kept separate from ORM models (clean architecture boundary).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Inbound (agent → API) ─────────────────────────────────────────────────────

class MetricPayload(BaseModel):
    """Payload posted by the monitoring agent every AGENT_INTERVAL seconds."""

    server_name: str = Field(..., min_length=1, max_length=255)
    timestamp: Optional[datetime] = None          # agent may omit; server fills in

    cpu_percent: float = Field(..., ge=0, le=100)
    memory_percent: float = Field(..., ge=0, le=100)
    memory_used_mb: float = Field(..., ge=0)
    memory_total_mb: float = Field(..., ge=0)
    disk_percent: float = Field(..., ge=0, le=100)
    disk_used_gb: float = Field(..., ge=0)
    disk_total_gb: float = Field(..., ge=0)

    net_bytes_sent: float = Field(..., ge=0)
    net_bytes_recv: float = Field(..., ge=0)

    uptime_seconds: float = Field(..., ge=0)
    process_count: int = Field(..., ge=0)

    @field_validator("server_name")
    @classmethod
    def strip_server_name(cls, v: str) -> str:
        return v.strip()


# ── Outbound (API → client) ───────────────────────────────────────────────────

class MetricResponse(BaseModel):
    id: int
    server_name: str
    timestamp: datetime

    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_total_gb: float

    net_bytes_sent: float
    net_bytes_recv: float

    uptime_seconds: float
    process_count: int

    model_config = {"from_attributes": True}


class ServerResponse(BaseModel):
    id: int
    name: str
    first_seen: datetime
    last_seen: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: int
    server_name: str
    timestamp: datetime
    metric_name: str
    metric_value: float
    threshold: float
    severity: str
    message: str
    resolved: bool

    model_config = {"from_attributes": True}


class DiagnoseResponse(BaseModel):
    server_name: str
    provider: str                  # gemini | openai | rule_based
    analysis: str
    suggestions: list[str]
    generated_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: bool
    version: str

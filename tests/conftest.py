"""Shared pytest fixtures for SmartOps tests."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SMARTOPS_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FILE", "")
os.environ.setdefault("SMARTOPS_API_KEY", "")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database.models import Base
from api.database.session import get_db
from api.main import app


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def api_client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_payload():
    return {
        "server_name": "test-server-01",
        "cpu_percent": 45.2,
        "memory_percent": 62.8,
        "memory_used_mb": 3200.0,
        "memory_total_mb": 8192.0,
        "disk_percent": 55.0,
        "disk_used_gb": 110.0,
        "disk_total_gb": 200.0,
        "net_bytes_sent": 102400,
        "net_bytes_recv": 204800,
        "uptime_seconds": 86400.0,
        "load_avg_1m": 1.2,
        "load_avg_5m": 0.9,
        "load_avg_15m": 0.7,
        "process_count": 142,
        "top_processes": [
            {"pid": 1234, "name": "nginx", "cpu_percent": 2.1,
             "memory_percent": 1.5, "status": "running"}
        ],
    }


@pytest.fixture
def critical_payload():
    return {
        "server_name": "critical-server",
        "cpu_percent": 95.5,
        "memory_percent": 92.3,
        "disk_percent": 88.0,
        "memory_used_mb": 7800.0,
        "memory_total_mb": 8192.0,
        "disk_used_gb": 176.0,
        "disk_total_gb": 200.0,
        "net_bytes_sent": 0,
        "net_bytes_recv": 0,
        "uptime_seconds": 3600.0,
        "load_avg_1m": 8.5,
        "load_avg_5m": 7.2,
        "load_avg_15m": 5.1,
        "process_count": 520,
        "top_processes": [],
    }

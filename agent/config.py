"""
Agent configuration — reads from environment variables and settings.yml.
"""

import os
import socket
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# Load YAML defaults
_settings_file = Path(__file__).parent.parent / "config" / "settings.yml"
_yaml_cfg: dict = {}
if _settings_file.exists():
    with open(_settings_file) as f:
        _yaml_cfg = yaml.safe_load(f) or {}

_agent_defaults = _yaml_cfg.get("agent", {})


class AgentConfig:
    """All configuration values for the monitoring agent."""

    # API endpoint
    API_URL: str = os.getenv(
        "AGENT_API_URL",
        _agent_defaults.get("api_url", "http://localhost:8000"),
    )
    METRICS_ENDPOINT: str = f"{API_URL}/api/metrics"

    # Collection interval
    INTERVAL: int = int(
        os.getenv("AGENT_INTERVAL", _agent_defaults.get("interval_seconds", 10))
    )

    # Server identity (default: hostname)
    SERVER_NAME: str = os.getenv(
        "AGENT_SERVER_NAME",
        _agent_defaults.get("server_name") or socket.gethostname(),
    )

    # Retry
    RETRY_ATTEMPTS: int = int(
        os.getenv("AGENT_RETRY_ATTEMPTS", _agent_defaults.get("retry_attempts", 3))
    )
    RETRY_DELAY: int = int(
        os.getenv("AGENT_RETRY_DELAY", _agent_defaults.get("retry_delay_seconds", 5))
    )
    TIMEOUT: int = int(
        os.getenv("AGENT_TIMEOUT", _agent_defaults.get("timeout_seconds", 10))
    )

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/agent.log")

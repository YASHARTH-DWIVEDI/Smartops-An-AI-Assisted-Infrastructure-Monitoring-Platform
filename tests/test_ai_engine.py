"""
Tests for ai_engine/ — rule-based engine and diagnostics dispatcher.
"""

import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai_engine.rules import RuleBasedEngine


HEALTHY_METRICS = {
    "cpu_percent": 30.0,
    "memory_percent": 45.0,
    "disk_percent": 40.0,
    "uptime_seconds": 86400,
    "process_count": 120,
    "load_avg_1m": 0.5,
    "load_avg_5m": 0.4,
    "load_avg_15m": 0.3,
    "net_bytes_sent": 1024,
    "net_bytes_recv": 2048,
}

CPU_CRITICAL_METRICS = dict(HEALTHY_METRICS, cpu_percent=95.0)
MEM_CRITICAL_METRICS = dict(HEALTHY_METRICS, memory_percent=93.0)
DISK_CRITICAL_METRICS = dict(HEALTHY_METRICS, disk_percent=88.0)
ALL_CRITICAL_METRICS = dict(HEALTHY_METRICS, cpu_percent=95.0, memory_percent=93.0, disk_percent=88.0)
CPU_WARNING_METRICS = dict(HEALTHY_METRICS, cpu_percent=78.0)
DISK_WARNING_METRICS = dict(HEALTHY_METRICS, disk_percent=72.0)


class TestRuleBasedEngine:
    def setup_method(self):
        self.engine = RuleBasedEngine()

    def test_healthy_metrics_return_healthy(self):
        result = self.engine.diagnose(HEALTHY_METRICS, "test-server")
        assert result["severity"] == "healthy"

    def test_cpu_critical_returns_critical(self):
        result = self.engine.diagnose(CPU_CRITICAL_METRICS, "test-server")
        assert result["severity"] == "critical"

    def test_memory_critical_returns_critical(self):
        result = self.engine.diagnose(MEM_CRITICAL_METRICS, "test-server")
        assert result["severity"] == "critical"

    def test_disk_critical_returns_critical(self):
        result = self.engine.diagnose(DISK_CRITICAL_METRICS, "test-server")
        assert result["severity"] == "critical"

    def test_all_critical_returns_critical(self):
        result = self.engine.diagnose(ALL_CRITICAL_METRICS, "test-server")
        assert result["severity"] == "critical"

    def test_cpu_warning_returns_warning(self):
        result = self.engine.diagnose(CPU_WARNING_METRICS, "test-server")
        assert result["severity"] == "warning"

    def test_result_has_required_keys(self):
        result = self.engine.diagnose(HEALTHY_METRICS, "test-server")
        for key in ("server_name", "provider", "severity", "summary", "causes", "recommendations"):
            assert key in result, f"Missing key: {key}"

    def test_result_provider_is_rules(self):
        result = self.engine.diagnose(HEALTHY_METRICS, "test-server")
        assert result["provider"] == "rules"

    def test_server_name_in_result(self):
        result = self.engine.diagnose(HEALTHY_METRICS, "my-server")
        assert result["server_name"] == "my-server"

    def test_critical_has_causes(self):
        result = self.engine.diagnose(CPU_CRITICAL_METRICS, "test-server")
        assert len(result["causes"]) > 0

    def test_critical_has_recommendations(self):
        result = self.engine.diagnose(CPU_CRITICAL_METRICS, "test-server")
        assert len(result["recommendations"]) > 0

    def test_healthy_has_no_causes(self):
        result = self.engine.diagnose(HEALTHY_METRICS, "test-server")
        assert result["causes"] == []

    def test_summary_non_empty(self):
        result = self.engine.diagnose(CPU_CRITICAL_METRICS, "test-server")
        assert len(result["summary"]) > 10

    def test_causes_are_strings(self):
        result = self.engine.diagnose(ALL_CRITICAL_METRICS, "test-server")
        for cause in result["causes"]:
            assert isinstance(cause, str)

    def test_recommendations_are_strings(self):
        result = self.engine.diagnose(ALL_CRITICAL_METRICS, "test-server")
        for rec in result["recommendations"]:
            assert isinstance(rec, str)

    def test_no_duplicate_causes(self):
        result = self.engine.diagnose(ALL_CRITICAL_METRICS, "test-server")
        assert len(result["causes"]) == len(set(result["causes"]))

    def test_no_duplicate_recommendations(self):
        result = self.engine.diagnose(ALL_CRITICAL_METRICS, "test-server")
        assert len(result["recommendations"]) == len(set(result["recommendations"]))

    def test_disk_warning_threshold(self):
        result = self.engine.diagnose(DISK_WARNING_METRICS, "test-server")
        assert result["severity"] in ("warning", "critical")

    def test_borderline_cpu_exactly_at_critical(self):
        metrics = dict(HEALTHY_METRICS, cpu_percent=90.0)
        result = self.engine.diagnose(metrics, "test-server")
        assert result["severity"] == "critical"

    def test_just_below_critical_is_warning(self):
        metrics = dict(HEALTHY_METRICS, cpu_percent=76.0)
        result = self.engine.diagnose(metrics, "test-server")
        assert result["severity"] == "warning"


class TestDiagnosticsEngine:
    """Tests for the dispatcher — only rule-based path (no Gemini key in tests)."""

    @pytest.mark.asyncio
    async def test_dispatcher_returns_result(self):
        from ai_engine.diagnostics import DiagnosticsEngine
        engine = DiagnosticsEngine()
        result = await engine.diagnose(HEALTHY_METRICS, "test-server")
        assert "severity" in result
        assert "provider" in result

    @pytest.mark.asyncio
    async def test_dispatcher_falls_back_to_rules_without_key(self):
        import os
        os.environ.pop("GEMINI_API_KEY", None)
        from ai_engine.diagnostics import DiagnosticsEngine
        engine = DiagnosticsEngine()
        result = await engine.diagnose(CPU_CRITICAL_METRICS, "test-server")
        assert result["provider"] == "rules"
        assert result["severity"] == "critical"

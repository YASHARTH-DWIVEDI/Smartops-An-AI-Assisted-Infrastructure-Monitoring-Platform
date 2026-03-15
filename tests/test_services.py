"""
Tests for API service layer (metrics + alerts).
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from datetime import datetime

from api.models.schemas import MetricPayload
from api.services.metrics_service import MetricsService, _compute_status
from api.services.alert_service import AlertService


# ── Helpers ───────────────────────────────────

def make_payload(**overrides) -> MetricPayload:
    base = {
        "server_name": "svc-test-server",
        "cpu_percent": 40.0,
        "memory_percent": 55.0,
        "disk_percent": 45.0,
    }
    base.update(overrides)
    return MetricPayload(**base)


# ── MetricsService ────────────────────────────

class TestMetricsService:
    def test_create_returns_record(self, db_session):
        payload = make_payload()
        record = MetricsService.create(db_session, payload)
        assert record.id is not None
        assert record.server_name == "svc-test-server"
        assert record.cpu_percent == 40.0

    def test_get_history_returns_list(self, db_session):
        MetricsService.create(db_session, make_payload())
        results = MetricsService.get_history(db_session)
        assert isinstance(results, list)

    def test_get_history_filtered_by_server(self, db_session):
        MetricsService.create(db_session, make_payload(server_name="server-A"))
        MetricsService.create(db_session, make_payload(server_name="server-B"))
        results = MetricsService.get_history(db_session, server_name="server-A")
        assert all(r.server_name == "server-A" for r in results)

    def test_get_history_limit_respected(self, db_session):
        for _ in range(10):
            MetricsService.create(db_session, make_payload())
        results = MetricsService.get_history(db_session, server_name="svc-test-server", limit=3)
        assert len(results) <= 3

    def test_get_servers_includes_created(self, db_session):
        MetricsService.create(db_session, make_payload(server_name="unique-server-xyz"))
        servers = MetricsService.get_servers(db_session)
        assert "unique-server-xyz" in servers

    def test_get_latest_per_server(self, db_session):
        MetricsService.create(db_session, make_payload(server_name="latest-test", cpu_percent=30.0))
        MetricsService.create(db_session, make_payload(server_name="latest-test", cpu_percent=60.0))
        summaries = MetricsService.get_latest_per_server(db_session)
        target = next((s for s in summaries if s.server_name == "latest-test"), None)
        assert target is not None
        # Should return most recent (cpu=60)
        assert target.cpu_percent == 60.0


class TestComputeStatus:
    def test_healthy(self):
        assert _compute_status(30, 40, 50) == "healthy"

    def test_warning_cpu(self):
        assert _compute_status(76, 40, 50) == "warning"

    def test_critical_cpu(self):
        assert _compute_status(91, 40, 50) == "critical"

    def test_critical_memory(self):
        assert _compute_status(30, 91, 50) == "critical"

    def test_critical_disk(self):
        assert _compute_status(30, 40, 86) == "critical"


# ── AlertService ──────────────────────────────

class TestAlertService:
    def setup_method(self):
        self.service = AlertService()

    def test_no_alerts_for_normal_metrics(self, db_session):
        payload = make_payload(cpu_percent=50, memory_percent=60, disk_percent=55)
        alerts = self.service.evaluate(db_session, payload)
        assert alerts == []

    def test_cpu_alert_created(self, db_session):
        payload = make_payload(server_name="alert-cpu-test", cpu_percent=95.0)
        alerts = self.service.evaluate(db_session, payload)
        cpu_alerts = [a for a in alerts if a.alert_type == "cpu"]
        assert len(cpu_alerts) >= 1

    def test_memory_alert_created(self, db_session):
        payload = make_payload(server_name="alert-mem-test", memory_percent=92.0)
        alerts = self.service.evaluate(db_session, payload)
        mem_alerts = [a for a in alerts if a.alert_type == "memory"]
        assert len(mem_alerts) >= 1

    def test_disk_alert_created(self, db_session):
        payload = make_payload(server_name="alert-disk-test", disk_percent=87.0)
        alerts = self.service.evaluate(db_session, payload)
        disk_alerts = [a for a in alerts if a.alert_type == "disk"]
        assert len(disk_alerts) >= 1

    def test_all_three_alerts_at_once(self, db_session):
        payload = make_payload(
            server_name="alert-all-test",
            cpu_percent=95.0,
            memory_percent=93.0,
            disk_percent=88.0,
        )
        alerts = self.service.evaluate(db_session, payload)
        alert_types = {a.alert_type for a in alerts}
        assert "cpu" in alert_types
        assert "memory" in alert_types
        assert "disk" in alert_types

    def test_alert_severity_is_critical(self, db_session):
        payload = make_payload(server_name="alert-sev-test", cpu_percent=95.0)
        alerts = self.service.evaluate(db_session, payload)
        for alert in alerts:
            if alert.alert_type == "cpu":
                assert alert.severity == "critical"

    def test_alert_metric_value_correct(self, db_session):
        payload = make_payload(server_name="alert-val-test", cpu_percent=94.5)
        alerts = self.service.evaluate(db_session, payload)
        cpu_alert = next((a for a in alerts if a.alert_type == "cpu"), None)
        assert cpu_alert is not None
        assert abs(cpu_alert.metric_value - 94.5) < 0.1

    def test_cooldown_prevents_duplicate_alerts(self, db_session):
        payload = make_payload(server_name="cooldown-test", cpu_percent=95.0)
        # First evaluation — should create alert
        first = self.service.evaluate(db_session, payload)
        # Immediate second evaluation — should be in cooldown
        second = self.service.evaluate(db_session, payload)
        cpu_second = [a for a in second if a.alert_type == "cpu"]
        assert len(cpu_second) == 0

    def test_get_alerts_returns_list(self, db_session):
        alerts = self.service.get_alerts(db_session)
        assert isinstance(alerts, list)

    def test_resolve_alert(self, db_session):
        payload = make_payload(server_name="resolve-test", cpu_percent=95.0)
        created = self.service.evaluate(db_session, payload)
        if created:
            alert_id = created[0].id
            resolved = self.service.resolve_alert(db_session, alert_id)
            assert resolved is not None
            assert resolved.resolved is True
            assert resolved.resolved_at is not None

    def test_resolve_nonexistent_returns_none(self, db_session):
        result = self.service.resolve_alert(db_session, 999999)
        assert result is None

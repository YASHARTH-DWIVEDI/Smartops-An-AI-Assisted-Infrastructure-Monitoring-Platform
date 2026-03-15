"""Tests for incident lifecycle management."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from api.models.schemas import MetricPayload
from api.services.incident_service import IncidentService


def make_payload(**kw) -> MetricPayload:
    base = {"server_name": "inc-test", "cpu_percent": 30.0,
            "memory_percent": 40.0, "disk_percent": 35.0}
    base.update(kw)
    return MetricPayload(**base)


@pytest.fixture
def svc():
    return IncidentService()


class TestIncidentService:
    def test_no_incident_for_normal(self, db_session, svc):
        created = svc.evaluate_and_create(db_session, make_payload())
        assert created == []

    def test_cpu_incident_created(self, db_session, svc):
        created = svc.evaluate_and_create(
            db_session, make_payload(server_name="inc-cpu", cpu_percent=95.0)
        )
        cpu = [i for i in created if i.alert_type == "cpu"]
        assert len(cpu) >= 1

    def test_disk_incident_created(self, db_session, svc):
        created = svc.evaluate_and_create(
            db_session, make_payload(server_name="inc-disk", disk_percent=88.0)
        )
        disk = [i for i in created if i.alert_type == "disk"]
        assert len(disk) >= 1

    def test_combined_incident_created(self, db_session, svc):
        created = svc.evaluate_and_create(
            db_session,
            make_payload(server_name="inc-combined", cpu_percent=85.0, memory_percent=85.0)
        )
        types = {i.alert_type for i in created}
        assert "combined" in types

    def test_severity_is_critical_above_threshold(self, db_session, svc):
        created = svc.evaluate_and_create(
            db_session, make_payload(server_name="inc-sev", cpu_percent=95.0)
        )
        cpu_inc = next((i for i in created if i.alert_type == "cpu"), None)
        assert cpu_inc is not None
        assert cpu_inc.severity == "critical"

    def test_cooldown_prevents_duplicate(self, db_session, svc):
        p = make_payload(server_name="inc-cooldown", cpu_percent=95.0)
        first  = svc.evaluate_and_create(db_session, p)
        second = svc.evaluate_and_create(db_session, p)
        cpu_second = [i for i in second if i.alert_type == "cpu"]
        assert len(cpu_second) == 0  # in cooldown

    def test_resolve_incident(self, db_session, svc):
        created = svc.evaluate_and_create(
            db_session, make_payload(server_name="inc-resolve", cpu_percent=95.0)
        )
        assert created
        inc = created[0]
        resolved = svc.resolve(db_session, inc.id, resolved_by="test-operator")
        assert resolved.resolved is True
        assert resolved.resolved_at is not None
        assert resolved.resolved_by == "test-operator"

    def test_resolve_records_duration(self, db_session, svc):
        created = svc.evaluate_and_create(
            db_session, make_payload(server_name="inc-dur", cpu_percent=95.0)
        )
        inc = created[0]
        resolved = svc.resolve(db_session, inc.id)
        assert resolved.duration_seconds is not None
        assert resolved.duration_seconds >= 0

    def test_auto_resolve(self, db_session, svc):
        svc.evaluate_and_create(
            db_session, make_payload(server_name="inc-auto", cpu_percent=95.0)
        )
        resolved = svc.auto_resolve(db_session, "inc-auto", "cpu")
        assert len(resolved) >= 1
        assert all(r.resolved_by == "auto" for r in resolved)

    def test_get_all_returns_list(self, db_session, svc):
        incidents = svc.get_all(db_session)
        assert isinstance(incidents, list)

    def test_get_stats_structure(self, db_session, svc):
        stats = svc.get_stats(db_session)
        for key in ("total", "open", "resolved", "critical", "warning", "mttr_minutes"):
            assert key in stats

    def test_resolve_nonexistent_returns_none(self, db_session, svc):
        result = svc.resolve(db_session, 999999)
        assert result is None

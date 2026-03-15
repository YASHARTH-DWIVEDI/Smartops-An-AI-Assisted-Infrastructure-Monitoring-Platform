"""Tests for server registration and health score calculation."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from api.services.server_service import (
    ServerService, compute_health_score, score_to_status
)


class TestHealthScore:
    def test_all_normal_gives_high_score(self):
        score = compute_health_score(cpu=30, mem=40, disk=50)
        assert score >= 85

    def test_perfect_metrics_score_100(self):
        score = compute_health_score(cpu=5, mem=10, disk=15)
        assert score == 100.0

    def test_cpu_critical_reduces_score(self):
        normal  = compute_health_score(cpu=10, mem=10, disk=10)
        high    = compute_health_score(cpu=96, mem=10, disk=10)
        assert high < normal

    def test_all_critical_gives_low_score(self):
        score = compute_health_score(cpu=96, mem=92, disk=91)
        assert score <= 25

    def test_score_floored_at_zero(self):
        score = compute_health_score(cpu=99, mem=99, disk=99)
        assert score >= 0.0

    def test_score_capped_at_100(self):
        score = compute_health_score(cpu=0, mem=0, disk=0)
        assert score <= 100.0

    def test_high_load_avg_reduces_score(self):
        no_load  = compute_health_score(cpu=50, mem=50, disk=50, load_avg=0.5, cpu_cores=4)
        high_load= compute_health_score(cpu=50, mem=50, disk=50, load_avg=10, cpu_cores=4)
        assert high_load < no_load


class TestScoreToStatus:
    def test_score_100_is_healthy(self):
        assert score_to_status(100) == "healthy"

    def test_score_80_is_healthy(self):
        assert score_to_status(80) == "healthy"

    def test_score_79_is_warning(self):
        assert score_to_status(79) == "warning"

    def test_score_50_is_warning(self):
        assert score_to_status(50) == "warning"

    def test_score_49_is_critical(self):
        assert score_to_status(49) == "critical"

    def test_score_0_is_critical(self):
        assert score_to_status(0) == "critical"


class TestServerService:
    def test_register_new_server(self, db_session):
        data = {
            "hostname": "test-web-01",
            "ip_address": "10.0.0.5",
            "os_name": "Linux",
            "os_version": "5.15.0",
            "cpu_cores": 4,
            "memory_total_mb": 8192.0,
        }
        server = ServerService.register(db_session, data)
        assert server.id is not None
        assert server.hostname == "test-web-01"
        assert server.ip_address == "10.0.0.5"
        assert server.cpu_cores == 4

    def test_re_register_updates_existing(self, db_session):
        data = {"hostname": "reregister-test", "ip_address": "10.0.0.1"}
        s1 = ServerService.register(db_session, data)
        s1_id = s1.id

        # Re-register with updated IP
        data2 = {"hostname": "reregister-test", "ip_address": "10.0.0.99"}
        s2 = ServerService.register(db_session, data2)

        assert s2.id == s1_id
        assert s2.ip_address == "10.0.0.99"

    def test_get_all_returns_list(self, db_session):
        servers = ServerService.get_all(db_session)
        assert isinstance(servers, list)

    def test_get_by_hostname(self, db_session):
        ServerService.register(db_session, {"hostname": "lookup-test"})
        found = ServerService.get_by_hostname(db_session, "lookup-test")
        assert found is not None
        assert found.hostname == "lookup-test"

    def test_get_by_hostname_not_found(self, db_session):
        found = ServerService.get_by_hostname(db_session, "does-not-exist")
        assert found is None

    def test_get_by_id(self, db_session):
        srv = ServerService.register(db_session, {"hostname": "id-lookup"})
        found = ServerService.get_by_id(db_session, srv.id)
        assert found is not None
        assert found.id == srv.id

"""
Tests for agent/collector.py

These tests use real psutil calls (no mocking) so they verify the collector
works on the current OS. They are skipped if psutil is unavailable.
"""

import pytest

pytest.importorskip("psutil")

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from agent.collector import MetricCollector, SystemMetrics


@pytest.fixture
def collector():
    return MetricCollector(server_name="test-server")


class TestMetricCollector:
    def test_collect_returns_system_metrics(self, collector):
        metrics = collector.collect()
        assert isinstance(metrics, SystemMetrics)

    def test_cpu_in_valid_range(self, collector):
        metrics = collector.collect()
        assert 0.0 <= metrics.cpu_percent <= 100.0

    def test_memory_in_valid_range(self, collector):
        metrics = collector.collect()
        assert 0.0 <= metrics.memory_percent <= 100.0

    def test_disk_in_valid_range(self, collector):
        metrics = collector.collect()
        assert 0.0 <= metrics.disk_percent <= 100.0

    def test_uptime_positive(self, collector):
        metrics = collector.collect()
        assert metrics.uptime_seconds > 0

    def test_memory_totals_consistent(self, collector):
        metrics = collector.collect()
        assert metrics.memory_used_mb <= metrics.memory_total_mb

    def test_disk_totals_consistent(self, collector):
        metrics = collector.collect()
        assert metrics.disk_used_gb <= metrics.disk_total_gb

    def test_server_name_preserved(self, collector):
        metrics = collector.collect()
        assert metrics.server_name == "test-server"

    def test_process_count_positive(self, collector):
        metrics = collector.collect()
        assert metrics.process_count > 0

    def test_top_processes_list(self, collector):
        metrics = collector.collect()
        assert isinstance(metrics.top_processes, list)
        assert len(metrics.top_processes) <= 5

    def test_to_dict_serializable(self, collector):
        metrics = collector.collect()
        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert "cpu_percent" in d
        assert "memory_percent" in d
        assert "disk_percent" in d
        assert "server_name" in d

    def test_network_delta_non_negative(self, collector):
        # First call initialises counters
        collector.collect()
        # Second call should give delta
        metrics = collector.collect()
        assert metrics.net_bytes_sent >= 0
        assert metrics.net_bytes_recv >= 0

    def test_load_avg_tuple(self, collector):
        metrics = collector.collect()
        assert metrics.load_avg_1m >= 0
        assert metrics.load_avg_5m >= 0
        assert metrics.load_avg_15m >= 0


class TestCollectorIsolation:
    def test_multiple_collectors_independent(self):
        c1 = MetricCollector("server-a")
        c2 = MetricCollector("server-b")
        m1 = c1.collect()
        m2 = c2.collect()
        assert m1.server_name == "server-a"
        assert m2.server_name == "server-b"

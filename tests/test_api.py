"""
Tests for the SmartOps FastAPI backend.
"""

import pytest


class TestHealthCheck:
    def test_health_returns_ok(self, api_client):
        r = api_client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestMetricsIngest:
    def test_post_valid_metrics(self, api_client, sample_payload):
        r = api_client.post("/api/metrics", json=sample_payload)
        assert r.status_code == 201
        data = r.json()
        assert data["status"] == "ok"
        assert "id=" in data["message"]

    def test_post_invalid_cpu(self, api_client, sample_payload):
        bad = dict(sample_payload, cpu_percent=105.0)
        r = api_client.post("/api/metrics", json=bad)
        assert r.status_code == 422

    def test_post_missing_server_name(self, api_client, sample_payload):
        bad = {k: v for k, v in sample_payload.items() if k != "server_name"}
        r = api_client.post("/api/metrics", json=bad)
        assert r.status_code == 422

    def test_post_minimal_payload(self, api_client):
        minimal = {
            "server_name": "minimal-server",
            "cpu_percent": 10.0,
            "memory_percent": 20.0,
            "disk_percent": 30.0,
        }
        r = api_client.post("/api/metrics", json=minimal)
        assert r.status_code == 201

    def test_post_critical_triggers_alert(self, api_client, critical_payload):
        r = api_client.post("/api/metrics", json=critical_payload)
        assert r.status_code == 201
        data = r.json()
        # Should mention alerts
        assert "Alerts:" in data["message"]


class TestMetricsQuery:
    def test_get_metrics_empty_initially(self, api_client):
        r = api_client.get("/api/metrics")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_metrics_after_post(self, api_client, sample_payload):
        api_client.post("/api/metrics", json=sample_payload)
        r = api_client.get("/api/metrics", params={"server": "test-server-01"})
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert data[0]["server_name"] == "test-server-01"

    def test_get_metrics_limit(self, api_client, sample_payload):
        for _ in range(5):
            api_client.post("/api/metrics", json=sample_payload)
        r = api_client.get("/api/metrics", params={"server": "test-server-01", "limit": 3})
        assert r.status_code == 200
        assert len(r.json()) <= 3

    def test_get_servers(self, api_client, sample_payload):
        api_client.post("/api/metrics", json=sample_payload)
        r = api_client.get("/api/metrics/servers")
        assert r.status_code == 200
        servers = r.json()
        assert isinstance(servers, list)
        assert "test-server-01" in servers

    def test_get_latest(self, api_client, sample_payload):
        api_client.post("/api/metrics", json=sample_payload)
        r = api_client.get("/api/metrics/latest")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        server_names = [s["server_name"] for s in data]
        assert "test-server-01" in server_names

    def test_get_latest_has_status(self, api_client, sample_payload):
        api_client.post("/api/metrics", json=sample_payload)
        r = api_client.get("/api/metrics/latest")
        item = next(
            (s for s in r.json() if s["server_name"] == "test-server-01"), None
        )
        assert item is not None
        assert item["status"] in ("healthy", "warning", "critical")

    def test_get_invalid_limit(self, api_client):
        r = api_client.get("/api/metrics", params={"limit": 9999})
        assert r.status_code == 422


class TestAlerts:
    def test_no_alerts_for_normal_metrics(self, api_client, sample_payload):
        api_client.post("/api/metrics", json=sample_payload)
        r = api_client.get("/api/alerts", params={"server": "test-server-01"})
        assert r.status_code == 200

    def test_alerts_created_for_critical(self, api_client, critical_payload):
        api_client.post("/api/metrics", json=critical_payload)
        r = api_client.get("/api/alerts", params={"server": "critical-server"})
        assert r.status_code == 200
        alerts = r.json()
        assert len(alerts) >= 1
        alert_types = {a["alert_type"] for a in alerts}
        assert "cpu" in alert_types

    def test_alert_has_correct_fields(self, api_client, critical_payload):
        api_client.post("/api/metrics", json=critical_payload)
        r = api_client.get("/api/alerts", params={"server": "critical-server"})
        for alert in r.json():
            assert "id" in alert
            assert "server_name" in alert
            assert "alert_type" in alert
            assert "severity" in alert
            assert "metric_value" in alert
            assert "threshold_value" in alert
            assert "resolved" in alert

    def test_alert_summary(self, api_client, critical_payload):
        api_client.post("/api/metrics", json=critical_payload)
        r = api_client.get("/api/alerts/summary")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_resolve_alert(self, api_client, critical_payload):
        api_client.post("/api/metrics", json=critical_payload)
        alerts_r = api_client.get("/api/alerts", params={"server": "critical-server", "resolved": "false"})
        alerts = alerts_r.json()
        if alerts:
            alert_id = alerts[0]["id"]
            resolve_r = api_client.put(f"/api/alerts/{alert_id}/resolve")
            assert resolve_r.status_code == 200
            assert resolve_r.json()["resolved"] is True

    def test_resolve_nonexistent_alert(self, api_client):
        r = api_client.put("/api/alerts/99999/resolve")
        assert r.status_code == 404


class TestSchemaValidation:
    def test_negative_cpu_rejected(self, api_client):
        r = api_client.post("/api/metrics", json={
            "server_name": "test", "cpu_percent": -1,
            "memory_percent": 50, "disk_percent": 50
        })
        assert r.status_code == 422

    def test_empty_server_name_rejected(self, api_client):
        r = api_client.post("/api/metrics", json={
            "server_name": "", "cpu_percent": 50,
            "memory_percent": 50, "disk_percent": 50
        })
        assert r.status_code == 422

    def test_cpu_over_100_rejected(self, api_client):
        r = api_client.post("/api/metrics", json={
            "server_name": "test", "cpu_percent": 101,
            "memory_percent": 50, "disk_percent": 50
        })
        assert r.status_code == 422

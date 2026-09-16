import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.core.metrics import metrics
from tests.conftest import create_test_auth_headers

client = TestClient(app)


def test_correlation_id_injection_and_propagation():
    """Verify that requests without correlation ID receive generated X-Correlation-ID in response."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "x-correlation-id" in response.headers
    cid = response.headers["x-correlation-id"]
    assert len(cid) > 10

    # Custom correlation ID is preserved
    custom_cid = "custom-trace-id-abc-123"
    custom_resp = client.get("/api/health", headers={"X-Correlation-ID": custom_cid})
    assert custom_resp.status_code == 200
    assert custom_resp.headers["x-correlation-id"] == custom_cid


def test_process_time_header():
    """Verify that X-Process-Time header indicates request latency in ms."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "x-process-time" in response.headers
    assert response.headers["x-process-time"].endswith("ms")


def test_prometheus_metrics_endpoint():
    """Verify that GET /metrics returns valid Prometheus exposition text."""
    # Perform a few requests to populate metrics
    client.get("/api/health")
    client.get("/")

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text_content = response.text

    assert "trustengine_http_requests_total" in text_content
    assert "trustengine_process_uptime_seconds" in text_content
    assert "trustengine_http_request_duration_seconds" in text_content


def test_observatory_metrics_json_endpoint():
    """Verify that GET /api/observatory/metrics returns structured telemetry JSON."""
    response = client.get("/api/observatory/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    m = data["data"]
    assert "uptime_seconds" in m
    assert "total_http_requests" in m
    assert isinstance(m["http_requests_breakdown"], list)


def test_readiness_and_liveness_probes(db_session: Session):
    """Verify Kubernetes/Docker readiness and liveness probes."""
    # Liveness probe
    live_res = client.get("/api/health/live")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "alive"

    # Readiness probe
    ready_res = client.get("/api/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"
    assert ready_res.json()["database_connections"] == "healthy"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from tests.conftest import create_test_auth_headers


def test_optimize_explain_endpoint(db_session: Session):
    """
    Test POST /api/optimize/explain returns plan summary, structured suggestions with confidence and copyable DDL.
    """
    client = TestClient(app)
    headers = create_test_auth_headers(db_session, role_name="admin", user_id=1)
    payload = {
        "sql": "SELECT first_name, last_name, salary FROM employees WHERE salary > 75000;",
        "role_name": "admin",
    }

    res = client.post("/api/optimize/explain", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "explain"
    assert "plan_summary" in data
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) > 0

    for s in data["suggestions"]:
        assert s["confidence"] in ["low", "medium", "high"]
        assert "observed" in s["evidence_json"]


def test_optimize_analyze_endpoint_role_gating(db_session: Session):
    """
    Test POST /api/optimize/analyze:
    - 403 Forbidden for role != 'admin'
    - 200 OK for role == 'admin'
    """
    client = TestClient(app)

    analyst_headers = create_test_auth_headers(db_session, role_name="analyst", user_id=11, email="analyst11@corp.com")
    admin_headers = create_test_auth_headers(db_session, role_name="admin", user_id=10, email="admin10@corp.com")

    # 1. Non-admin request -> 403 Forbidden
    non_admin_payload = {
        "sql": "SELECT * FROM products WHERE unit_price > 50;",
    }
    res_forbidden = client.post("/api/optimize/analyze", json=non_admin_payload, headers=analyst_headers)
    assert res_forbidden.status_code == 403
    assert "Access denied" in res_forbidden.json()["detail"]

    # 2. Admin request -> 200 OK
    admin_payload = {
        "sql": "SELECT * FROM products WHERE unit_price > 50;",
    }
    res_ok = client.post("/api/optimize/analyze", json=admin_payload, headers=admin_headers)
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["mode"] == "explain_analyze"
    assert "execution_stats" in data
    assert len(data["suggestions"]) > 0


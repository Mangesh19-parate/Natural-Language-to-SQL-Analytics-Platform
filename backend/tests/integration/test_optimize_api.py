import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.models.auth import Role, User


@pytest.fixture
def seed_optimize_db(db_session: Session):
    role_admin = Role(role_id=1, role_name="admin")
    role_analyst = Role(role_id=2, role_name="analyst")
    user_test = User(user_id=1, full_name="Test Analyst", email="analyst@corp.com", password_hash="dummy", role_id=2)
    db_session.add_all([role_admin, role_analyst, user_test])
    db_session.commit()
    return db_session



def test_optimize_explain_endpoint(seed_optimize_db):
    """
    Test POST /api/optimize/explain returns plan summary, structured suggestions with confidence and copyable DDL.
    """
    client = TestClient(app)
    payload = {
        "sql": "SELECT first_name, last_name, salary FROM employees WHERE salary > 75000;",
        "role_name": "analyst",
    }

    res = client.post("/api/optimize/explain", json=payload)
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


def test_optimize_analyze_endpoint_role_gating(seed_optimize_db):
    """
    Test POST /api/optimize/analyze:
    - 403 Forbidden for role != 'admin'
    - 200 OK for role == 'admin'
    """
    client = TestClient(app)

    # 1. Non-admin request -> 403 Forbidden
    non_admin_payload = {
        "sql": "SELECT * FROM products WHERE unit_price > 50;",
        "role_name": "analyst",
    }
    res_forbidden = client.post("/api/optimize/analyze", json=non_admin_payload)
    assert res_forbidden.status_code == 403
    assert "restricted to administrators" in res_forbidden.json()["detail"]

    # 2. Admin request -> 200 OK
    admin_payload = {
        "sql": "SELECT * FROM products WHERE unit_price > 50;",
        "role_name": "admin",
    }
    res_ok = client.post("/api/optimize/analyze", json=admin_payload)
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["mode"] == "explain_analyze"
    assert "execution_stats" in data
    assert len(data["suggestions"]) > 0

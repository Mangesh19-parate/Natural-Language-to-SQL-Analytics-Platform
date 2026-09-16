import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role
from app.models.lab import FailureLog
from app.models.session import QueryHistory
from tests.conftest import create_test_auth_headers


client = TestClient(app)


@pytest.fixture
def seed_observatory_data(db_session: Session):
    """Seeds failure records and query history for observatory analytics."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Observatory DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    # Seed failure logs across multiple failure classes and problematic phrases
    failures = [
        FailureLog(
            failure_class="schema_mismatch",
            problematic_phrase="total turnover",
        ),
        FailureLog(
            failure_class="schema_mismatch",
            problematic_phrase="turnover regional",
        ),
        FailureLog(
            failure_class="policy_violation",
            problematic_phrase="drop table",
        ),
        FailureLog(
            failure_class="policy_violation",
            problematic_phrase="employee salary",
        ),
        FailureLog(
            failure_class="syntax_error",
            problematic_phrase="select from where",
        ),
        FailureLog(
            failure_class="unsupported_intent",
            problematic_phrase="weather tokyo",
        ),
        FailureLog(
            failure_class="empty_result_anomaly",
            problematic_phrase="active subscribers",
        ),
        FailureLog(
            failure_class="timeout",
            problematic_phrase="massive transaction",
        ),
        FailureLog(
            failure_class="critic_rejection",
            problematic_phrase="heuristic score",
        ),
        FailureLog(
            failure_class="semantic_drift",
            problematic_phrase="profit margin denominator",
        ),
    ]
    for f in failures:
        db_session.add(f)

    # Also seed a query history record
    db_session.add(QueryHistory(
        nl_question="Show total sales revenue",
        final_sql="SELECT SUM(revenue) FROM sales",
        status="success",
        row_count=1,
    ))

    db_session.commit()

    headers = create_test_auth_headers(db_session, role_name="admin")

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "total_failures": len(failures),
        "headers": headers,
    }

    app.dependency_overrides.clear()


def test_observatory_stats_endpoint(seed_observatory_data: dict):
    """Test GET /api/observatory/stats returns aggregated taxonomy breakdown and interventions."""
    headers = seed_observatory_data["headers"]
    response = client.get("/api/observatory/stats", headers=headers)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]

    assert data["total_failures"] >= 10
    assert len(data["failure_classes"]) >= 7

    # Verify percentages sum to ~100%
    total_pct = sum(b["percentage"] for b in data["failure_classes"])
    assert 98.0 <= total_pct <= 101.0

    # Verify top recommended intervention
    assert data["top_recommended_intervention"] is not None


def test_observatory_phrases_endpoint(seed_observatory_data: dict):
    """Test GET /api/observatory/phrases clusters problematic n-grams."""
    headers = seed_observatory_data["headers"]
    response = client.get("/api/observatory/phrases", headers=headers)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    phrases = res["data"]

    assert isinstance(phrases, list)
    assert len(phrases) > 0

    phrase_texts = [p["phrase"] for p in phrases]
    assert any("turnover" in p or "salary" in p or "drop" in p for p in phrase_texts)


def test_observatory_logs_endpoint(seed_observatory_data: dict):
    """Test GET /api/observatory/logs."""
    headers = seed_observatory_data["headers"]
    res_all = client.get("/api/observatory/logs?limit=20", headers=headers)
    assert res_all.status_code == 200
    res = res_all.json()
    assert res["success"] is True
    logs_all = res["data"]
    assert len(logs_all) >= 10


def test_observatory_log_event_api(seed_observatory_data: dict):
    """Test POST /api/observatory/log inserts a new failure record."""
    headers = seed_observatory_data["headers"]
    payload = {
        "failure_class": "schema_mismatch",
        "problematic_phrase": "network latency average",
    }
    response = client.post("/api/observatory/log", json=payload, headers=headers)
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    assert res["data"]["failure_id"] > 0
    assert res["data"]["failure_class"] == "schema_mismatch"

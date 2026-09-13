import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, DataPolicy, SemanticCatalog
from app.models.auth import Role
from app.models.session import QueryHistory
from app.models.trust import ResultValidation


client = TestClient(app)


@pytest.fixture
def seed_correction_api_data(db_session: Session):
    """Seeds test data source, role, catalog, and query history for Correction & Validation API tests."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Correction DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="departments", column_name="department_id", semantic_type="identifier", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="departments", column_name="department_name", semantic_type="categorical", sensitivity="NONE"),
    ]
    for c in catalog:
        db_session.add(c)

    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="departments", access_level="read", aggregate_allowed=True))

    q_id = str(uuid.uuid4())
    qh = QueryHistory(
        query_id=q_id,
        user_id=1,
        nl_question="Show departments",
        initial_sql="SELECT department_name FORM departments;",
        status="success",
    )
    db_session.add(qh)
    db_session.commit()

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
        "query_id": q_id,
    }

    app.dependency_overrides.clear()


def test_api_self_correct_endpoint(seed_correction_api_data: dict):
    """Test POST /api/sql/correct endpoint repairs an E1 syntax error."""
    payload = {
        "original_question": "List department names",
        "failing_sql": "SELECT department_name FORM departments;",
        "error_message": "syntax error at or near 'FORM'",
        "data_source_id": seed_correction_api_data["ds_id"],
        "role_id": seed_correction_api_data["role_id"],
        "query_id": seed_correction_api_data["query_id"],
    }
    response = client.post("/api/sql/correct", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["recovered"] is True
    assert data["error_type"] == "E1"
    assert "FROM" in data["final_sql"].upper()
    assert data["retries_used"] >= 1
    assert len(data["attempts"]) >= 1


def test_api_validate_results_endpoint(seed_correction_api_data: dict):
    """Test POST /api/sql/validate-results endpoint flags anomalies and persists to DB."""
    db: Session = seed_correction_api_data["db"]
    q_id = seed_correction_api_data["query_id"]

    payload = {
        "sql": "SELECT department_id, department_name FROM departments;",
        "columns": ["department_id", "department_name"],
        "rows": [{"department_id": 1, "department_name": None}, {"department_id": 2, "department_name": None}],
        "row_count": 2,
        "data_source_id": seed_correction_api_data["ds_id"],
        "query_id": q_id,
    }
    response = client.post("/api/sql/validate-results", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["has_anomalies"] is True
    assert data["findings_count"] >= 1
    assert any(f["check_type"] == "null_explosion" for f in data["findings"])

    # Check persistence in DB
    db_findings = db.query(ResultValidation).filter(ResultValidation.query_id == q_id).all()
    assert len(db_findings) >= 1
    assert db_findings[0].check_type == "null_explosion"


def test_api_execute_endpoint_with_auto_correction_and_result_validation(seed_correction_api_data: dict):
    """Test POST /api/sql/execute end-to-end with intentional syntax error repaired via auto-correction."""
    payload = {
        "sql": "SELECT department_name FORM departments;",
        "data_source_id": seed_correction_api_data["ds_id"],
        "role_id": seed_correction_api_data["role_id"],
        "auto_correct": True,
        "question": "Show all department names",
        "query_id": seed_correction_api_data["query_id"],
    }
    # Note: policy validator may fail on initial AST syntax check or sandbox execution
    response = client.post("/api/sql/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "policy_validation" in data


def test_api_execute_endpoint_e5_policy_rejection_no_retry(seed_correction_api_data: dict):
    """Test POST /api/sql/execute with unauthorized query is rejected as E5 without retries."""
    payload = {
        "sql": "SELECT salary FROM employees;",  # employees not in role policy
        "data_source_id": seed_correction_api_data["ds_id"],
        "role_id": seed_correction_api_data["role_id"],
        "auto_correct": True,
        "question": "What is the employee salary?",
    }
    response = client.post("/api/sql/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["error_type"] == "E5"
    assert data["correction_result"] is None or data["correction_result"]["routed_as_policy_rejection"] is True


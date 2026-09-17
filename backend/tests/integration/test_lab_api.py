import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role
from tests.conftest import create_test_auth_headers


client = TestClient(app)


@pytest.fixture
def seed_lab_api_data(db_session: Session):
    """Seeds test data source, role, policies, and catalog for Lab API endpoints."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Enterprise DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    role_viewer = Role(role_name="viewer")
    db_session.add_all([ds, role_admin, role_viewer])
    db_session.flush()

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="city", semantic_type="location", sensitivity="LOW"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="total_spent", semantic_type="currency", sensitivity="LOW"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="sale_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="revenue", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"),
    ]
    for c in catalog:
        db_session.add(c)

    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="customers", access_level="read", aggregate_allowed=True))
    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="sales", access_level="read", aggregate_allowed=True))
    db_session.commit()

    headers = create_test_auth_headers(db_session, role_name="admin")

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
        "headers": headers,
    }

    app.dependency_overrides.clear()


def test_security_attack_run_api(seed_lab_api_data: dict):
    """Test POST /api/lab/security/run executes the standing adversarial suite."""
    headers = seed_lab_api_data["headers"]
    payload = {
        "data_source_id": seed_lab_api_data["ds_id"]
    }
    response = client.post("/api/lab/security/run", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total_attacks"] >= 128
    assert data["total_blocked"] == data["total_attacks"]
    assert data["total_unblocked"] == 0
    assert data["safety_violation_rate"] == 0.0
    assert data["status"] == "PASSED"
    assert len(data["results"]) == data["total_attacks"]


def test_security_attack_latest_api(seed_lab_api_data: dict):
    """Test GET /api/lab/security/latest retrieves stored results without re-execution."""
    headers = seed_lab_api_data["headers"]
    # 1. Clean state before run
    res_clean = client.get("/api/lab/security/latest", headers=headers)
    assert res_clean.status_code == 200
    data_clean = res_clean.json()
    assert data_clean["status"] == "NOT_YET_RUN"
    assert data_clean["total_attacks"] == 0

    # 2. Execute run
    client.post("/api/lab/security/run", json={"data_source_id": seed_lab_api_data["ds_id"]}, headers=headers)

    # 3. Retrieve latest stored run
    response = client.get("/api/lab/security/latest", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_attacks"] >= 128
    assert data["total_blocked"] == data["total_attacks"]
    assert data["status"] == "PASSED"


def test_evaluation_run_api(seed_lab_api_data: dict):
    """Test POST /api/lab/evaluation/run executes benchmark comparing baseline variants."""
    headers = seed_lab_api_data["headers"]
    payload = {
        "data_source_id": seed_lab_api_data["ds_id"],
        "categories": ["simple", "adversarial"],
        "baseline_variants": ["A_plain_llm", "D_proposed"],
    }
    response = client.post("/api/lab/evaluation/run", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total_questions"] > 0
    assert len(data["category_breakdown"]) == 2
    assert "overall_metrics" in data
    assert data["overall_metrics"]["baseline_d_overall_safety_violation_rate"] == 0.0


def test_evaluation_latest_api(seed_lab_api_data: dict):
    """Test GET /api/lab/evaluation/latest retrieves stored evaluation matrix without re-execution."""
    headers = seed_lab_api_data["headers"]
    # 1. Clean state before run
    res_clean = client.get("/api/lab/evaluation/latest", headers=headers)
    assert res_clean.status_code == 200
    data_clean = res_clean.json()
    assert data_clean["total_questions"] == 0
    assert data_clean["overall_metrics"]["status"] == "No benchmark runs executed yet"

    # 2. Execute a benchmark run
    payload = {
        "data_source_id": seed_lab_api_data["ds_id"],
        "categories": ["simple", "adversarial"],
        "baseline_variants": ["A_plain_llm", "D_proposed"],
    }
    client.post("/api/lab/evaluation/run", json=payload, headers=headers)

    # 3. Retrieve stored latest run
    response = client.get("/api/lab/evaluation/latest", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] > 0
    assert len(data["category_breakdown"]) > 0
    assert data["overall_metrics"]["baseline_d_overall_safety_violation_rate"] == 0.0

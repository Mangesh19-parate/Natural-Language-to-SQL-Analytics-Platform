import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataPolicy, SemanticCatalog, DataSource
from app.models.auth import Role


client = TestClient(app)


@pytest.fixture
def seed_sql_api_data(db_session: Session):
    """Seeds test data source, role, policies, and catalog for API endpoints."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Enterprise DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_analyst = Role(role_name="analyst")
    db_session.add_all([ds, role_analyst])
    db_session.flush()

    # Seed catalog
    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="sale_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="sale_amount", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="ssn", semantic_type="identifier", sensitivity="HIGH"),
    ]
    for c in catalog:
        db_session.add(c)

    # Policy for Role Analyst: Access to sales and customers, but ssn is denied
    db_session.add(DataPolicy(role_id=role_analyst.role_id, data_source_id=ds.data_source_id, table_name="sales", access_level="read", aggregate_allowed=True))
    db_session.add(DataPolicy(role_id=role_analyst.role_id, data_source_id=ds.data_source_id, table_name="customers", access_level="read", aggregate_allowed=False))
    db_session.add(DataPolicy(role_id=role_analyst.role_id, data_source_id=ds.data_source_id, table_name="customers", column_name="ssn", access_level="denied"))

    db_session.commit()

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_analyst.role_id,
    }

    app.dependency_overrides.clear()


def test_api_generate_sql_success(seed_sql_api_data: dict):
    """Test POST /api/sql/generate with authorized role."""
    payload = {
        "question": "What is the sum of sales?",
        "role_id": seed_sql_api_data["role_id"],
        "data_source_id": seed_sql_api_data["ds_id"]
    }
    response = client.post("/api/sql/generate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["can_execute"] is True
    assert data["policy_validation"]["status"] == "APPROVED"
    assert "proposal" in data
    assert data["proposal"]["is_proposal"] is True
    assert "SELECT" in data["proposal"]["sql"].upper()


def test_api_validate_sql_select_only(seed_sql_api_data: dict):
    """Test POST /api/sql/validate blocking DROP statements."""
    payload = {
        "sql": "DROP TABLE sales;",
        "role_id": seed_sql_api_data["role_id"],
        "data_source_id": seed_sql_api_data["ds_id"]
    }
    response = client.post("/api/sql/validate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["policy_validation"]["is_allowed"] is False
    assert data["policy_validation"]["status"] == "REJECTED"
    assert any(v["violation_type"] == "STATEMENT_NOT_ALLOWED" for v in data["policy_validation"]["violations"])


def test_api_validate_sql_unauthorized_column(seed_sql_api_data: dict):
    """Test POST /api/sql/validate blocking access to denied SSN column."""
    payload = {
        "sql": "SELECT customer_name, ssn FROM customers;",
        "role_id": seed_sql_api_data["role_id"],
        "data_source_id": seed_sql_api_data["ds_id"]
    }
    response = client.post("/api/sql/validate", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["policy_validation"]["is_allowed"] is False
    assert data["policy_validation"]["status"] == "REJECTED"
    assert any(
        v["violation_type"] == "UNAUTHORIZED_COLUMN" and v["column_name"] == "ssn"
        for v in data["policy_validation"]["violations"]
    )

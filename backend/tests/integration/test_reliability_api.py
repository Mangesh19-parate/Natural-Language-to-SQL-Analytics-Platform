import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.session import QueryHistory
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role


client = TestClient(app)


@pytest.fixture
def seed_reliability_api_data(db_session: Session):
    """Seeds test data source, role, policies, and catalog for API endpoints."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Enterprise DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    # Seed catalog
    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="city", semantic_type="location", sensitivity="LOW"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="total_spent", semantic_type="currency", sensitivity="LOW"),
    ]
    for c in catalog:
        db_session.add(c)

    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="customers", access_level="read", aggregate_allowed=True))
    db_session.commit()

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
    }

    app.dependency_overrides.clear()


def test_execute_endpoint_attaches_reliability_breakdown(seed_reliability_api_data: dict):
    """Verify that /api/sql/execute returns a complete, deterministic reliability breakdown."""
    payload = {
        "sql": "SELECT customer_name, city FROM customers WHERE total_spent > 100",
        "data_source_id": seed_reliability_api_data["ds_id"],
        "role_id": seed_reliability_api_data["role_id"],
        "auto_correct": True,
    }
    response = client.post("/api/sql/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "reliability_breakdown" in data
    
    rb = data["reliability_breakdown"]
    assert rb is not None
    assert "composite_score" in rb
    assert "tier" in rb
    assert "status_label" in rb
    assert rb["composite_score"] >= 80
    assert rb["tier"] == "HIGH"
    
    # Verify all 5 sub-scores are present and structured
    for key in ["schema_grounding", "join_confidence", "filter_interpretation", "execution_validation", "result_sanity"]:
        assert key in rb
        assert "score" in rb[key]
        assert "tier" in rb[key]
        assert "weight" in rb[key]
        assert "status_icon" in rb[key]
        assert "summary" in rb[key]
        assert "evidence_items" in rb[key]
        assert isinstance(rb[key]["evidence_items"], list)


def test_execute_endpoint_persists_reliability_breakdown(seed_reliability_api_data: dict):
    """Verify that query_history records the reliability_breakdown payload."""
    db_session = seed_reliability_api_data["db"]
    query_id = "test-q-rel-001"
    q_hist = QueryHistory(
        query_id=query_id,
        nl_question="Show customer names and cities",
        status="pending",
    )
    db_session.add(q_hist)
    db_session.commit()

    payload = {
        "sql": "SELECT customer_name, city FROM customers LIMIT 10",
        "data_source_id": seed_reliability_api_data["ds_id"],
        "role_id": seed_reliability_api_data["role_id"],
        "query_id": query_id,
    }
    response = client.post("/api/sql/execute", json=payload)
    assert response.status_code == 200
    
    # Reload and verify DB persistence
    db_session.refresh(q_hist)
    assert q_hist.status == "success"
    assert q_hist.reliability_breakdown is not None
    assert "composite_score" in q_hist.reliability_breakdown
    assert q_hist.reliability_breakdown["composite_score"] >= 80


def test_generate_endpoint_attaches_pre_execution_reliability(seed_reliability_api_data: dict):
    """Verify that /api/sql/generate includes pre-execution reliability evaluation."""
    payload = {
        "question": "Show top 5 customers by total spent",
        "data_source_id": seed_reliability_api_data["ds_id"],
        "role_id": seed_reliability_api_data["role_id"],
    }
    response = client.post("/api/sql/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "reliability_breakdown" in data
    assert data["reliability_breakdown"] is not None
    assert data["reliability_breakdown"]["composite_score"] > 0


def test_execute_policy_rejection_reliability(seed_reliability_api_data: dict):
    """Verify that policy rejections produce LOW reliability breakdown."""
    payload = {
        "sql": "DROP TABLE customers",
        "data_source_id": seed_reliability_api_data["ds_id"],
        "role_id": seed_reliability_api_data["role_id"],
    }
    response = client.post("/api/sql/execute", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["reliability_breakdown"]["tier"] == "LOW"
    assert data["reliability_breakdown"]["execution_validation"]["score"] == 0
    assert data["reliability_breakdown"]["execution_validation"]["status_icon"] == "✗"

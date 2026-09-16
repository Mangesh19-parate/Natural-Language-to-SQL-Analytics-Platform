import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, DataPolicy, SemanticCatalog
from app.models.auth import Role, User
from app.models.session import QueryHistory
from app.models.trust import SqlCriticFinding
from app.services.sql_critic import SQLCriticService
from tests.conftest import create_test_auth_headers


client = TestClient(app)


@pytest.fixture
def seed_critic_api_data(db_session: Session):
    """Seeds test data source, role, catalog, and query history for Critic API tests."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Critic DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    headers = create_test_auth_headers(db_session, role_name="admin", user_id=60, email="admin_critic@test.com")

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="orders", column_name="order_id", semantic_type="identifier", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="orders", column_name="total_amount", semantic_type="monetary", sensitivity="NONE"),
    ]
    for c in catalog:
        db_session.add(c)

    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="orders", access_level="read", aggregate_allowed=True))

    # Query history record to attach findings to
    q_id = str(uuid.uuid4())
    qh = QueryHistory(
        query_id=q_id,
        user_id=60,
        nl_question="What is the sum of order ids?",
        initial_sql="SELECT SUM(order_id) FROM orders;",
        status="success",
    )
    db_session.add(qh)
    db_session.commit()

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
        "query_id": q_id,
        "headers": headers,
    }

    app.dependency_overrides.clear()


def test_api_critic_endpoint(seed_critic_api_data: dict):
    """Test POST /api/sql/critic endpoint detects smell and returns structured findings."""
    payload = {
        "sql": "SELECT SUM(order_id) FROM orders;",
        "data_source_id": seed_critic_api_data["ds_id"],
        "role_id": seed_critic_api_data["role_id"],
        "query_id": seed_critic_api_data["query_id"],
    }
    response = client.post("/api/sql/critic", json=payload, headers=seed_critic_api_data["headers"])
    assert response.status_code == 200
    data = response.json()

    assert "critic_analysis" in data
    assert data["critic_analysis"]["has_findings"] is True
    assert data["critic_analysis"]["findings_count"] >= 1
    
    finding = data["critic_analysis"]["findings"][0]
    assert finding["finding_type"] == "aggregate_on_identifier"
    assert "suggested_sql" in finding
    assert "COUNT" in finding["suggested_sql"].upper()


def test_sql_critic_findings_persistence(seed_critic_api_data: dict):
    """Verifies that findings are persisted into the sql_critic_findings table (Task T-24)."""
    db: Session = seed_critic_api_data["db"]
    q_id = seed_critic_api_data["query_id"]

    # Call endpoint with query_id to trigger persistence
    payload = {
        "sql": "SELECT SUM(order_id) FROM orders;",
        "data_source_id": seed_critic_api_data["ds_id"],
        "role_id": seed_critic_api_data["role_id"],
        "query_id": q_id,
    }
    client.post("/api/sql/critic", json=payload, headers=seed_critic_api_data["headers"])

    # Query DB table
    db_findings = db.query(SqlCriticFinding).filter(SqlCriticFinding.query_id == q_id).all()
    assert len(db_findings) >= 1
    assert db_findings[0].finding_type == "aggregate_on_identifier"
    assert db_findings[0].suggested_fix is not None


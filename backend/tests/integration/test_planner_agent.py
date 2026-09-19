import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role
from app.services.planner_agent import PlannerAgentService
from scripts.seed_business_db import seed_business_database


client = TestClient(app)


@pytest.fixture
def seed_planner_agent_data(db_session: Session):
    """Seeds test data source, roles, and policies for Planner Agent integration tests."""
    seed_business_database()
    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Planner DB", db_type="sqlite", secret_ref="sqlite:///./local_data/business.db", is_active=True)
    role_admin = Role(role_name="admin")
    role_viewer = Role(role_name="viewer")
    db_session.add_all([ds, role_admin, role_viewer])
    db_session.flush()

    tables = ["customers", "departments", "employees", "products", "orders", "sales"]
    for t in tables:
        db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name=t, column_name="id", semantic_type="id", sensitivity="NONE"))
        db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name=t, access_level="read", aggregate_allowed=True))

    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"))
    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="total_spent", semantic_type="currency", sensitivity="LOW"))
    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="revenue", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"))
    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="sale_date", semantic_type="temporal", sensitivity="NONE"))

    # For Viewer: only customers is accessible, sales is denied
    db_session.add(DataPolicy(role_id=role_viewer.role_id, data_source_id=ds.data_source_id, table_name="customers", access_level="read", aggregate_allowed=True))

    db_session.commit()

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "admin_role_id": role_admin.role_id,
        "viewer_role_id": role_viewer.role_id,
    }

    app.dependency_overrides.clear()


from tests.conftest import create_test_auth_headers


def test_compound_query_detection():
    """Verify PlannerAgentService identifies compound and multi-step analytical intents."""
    assert PlannerAgentService.is_compound_query("Compare revenue from 2023 vs 2024 and calculate growth") is True
    assert PlannerAgentService.is_compound_query("Compare top 5 and bottom 5 customers by total spending") is True
    assert PlannerAgentService.is_compound_query("Show total sales revenue") is False


def test_compound_query_decomposition():
    """Verify PlannerAgentService breaks compound queries into DAG sub-tasks."""
    sub_tasks = PlannerAgentService.decompose_compound_query("Compare revenue from 2023 vs 2024 and calculate growth")
    assert len(sub_tasks) == 3
    assert sub_tasks[0].step_id == 1
    assert sub_tasks[1].step_id == 2
    assert sub_tasks[2].step_id == 3
    assert sub_tasks[2].dependencies == [1, 2]


def test_planner_agent_execution_authorized(seed_planner_agent_data: dict):
    """Test POST /api/agent/execute with authorized admin role executes DAG and returns synthesized answer."""
    headers = create_test_auth_headers(seed_planner_agent_data["db"], role_name="admin", user_id=1)
    payload = {
        "question": "Compare revenue from 2023 vs 2024 and calculate growth",
        "role_id": seed_planner_agent_data["admin_role_id"],
        "data_source_id": seed_planner_agent_data["ds_id"],
    }
    response = client.post("/api/agent/execute", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    plan = data["data"]
    assert plan["is_compound"] is True
    assert plan["overall_status"] == "COMPLETED"
    assert plan["all_steps_authorized"] is True
    assert len(plan["step_results"]) == 3
    assert plan["synthesized_answer"] is not None


def test_planner_agent_execution_policy_blocked(seed_planner_agent_data: dict):
    """
    Test POST /api/agent/execute with viewer role attempting to access unauthorized sales table
    is strictly blocked by the Policy Engine (Rule R6.1).
    """
    headers = create_test_auth_headers(seed_planner_agent_data["db"], role_name="viewer", user_id=2)
    payload = {
        "question": "Compare revenue from 2023 vs 2024 and calculate growth",
        "role_id": seed_planner_agent_data["viewer_role_id"],
        "data_source_id": seed_planner_agent_data["ds_id"],
    }
    response = client.post("/api/agent/execute", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True

    plan = data["data"]
    assert plan["overall_status"] == "POLICY_BLOCKED"
    assert plan["all_steps_authorized"] is False
    assert any(not step["policy_allowed"] for step in plan["step_results"])

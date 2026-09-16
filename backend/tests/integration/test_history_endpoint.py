import uuid
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.session import get_db
from app.models.session import QueryHistory, SessionModel
from app.models.trust import SqlCriticFinding, ResultValidation
from app.models.policy import DataSource, DataPolicy, SemanticCatalog
from app.models.auth import Role, User
from tests.conftest import create_test_auth_headers

client = TestClient(app)


@pytest.fixture
def seed_history_data(db_session):
    """Seeds test data for history tests and wires get_db override."""
    app.dependency_overrides[get_db] = lambda: db_session

    ds = db_session.query(DataSource).first()
    if not ds:
        ds = DataSource(name="History Test DB", db_type="sqlite", secret_ref="local", is_active=True)
        db_session.add(ds)

    role_admin = db_session.query(Role).filter(Role.role_name == "admin").first()
    if not role_admin:
        role_admin = Role(role_name="admin")
        db_session.add(role_admin)

    db_session.flush()

    headers = create_test_auth_headers(db_session, role_name="admin", user_id=40, email="admin_history@test.com")

    # Ensure admin has access to products and orders
    db_session.add_all([
        DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="products", access_level="read", aggregate_allowed=True),
        DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="departments", access_level="read", aggregate_allowed=True),
        DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="employees", access_level="read", aggregate_allowed=True),
    ])

    q_id = str(uuid.uuid4())
    q_item = QueryHistory(
        query_id=q_id,
        user_id=40,
        nl_question="Show total revenue by department",
        final_sql="SELECT d.department_name, SUM(e.salary) FROM departments d JOIN employees e ON d.department_id = e.department_id GROUP BY d.department_name",
        status="success",
        classification="answerable",
        execution_ms=45,
        row_count=5,
        reliability_breakdown={"composite": 94.0, "schema_grounding": 100.0},
    )
    db_session.add(q_item)
    db_session.commit()

    yield {
        "db": db_session,
        "query_id": q_id,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
        "headers": headers,
    }

    app.dependency_overrides.clear()


def test_query_history_list_and_detail(seed_history_data):
    q_id = seed_history_data["query_id"]
    headers = seed_history_data["headers"]

    # 1. Test List
    res_list = client.get("/api/history?page=1&page_size=10", headers=headers)
    assert res_list.status_code == 200
    data = res_list.json()["data"]
    assert data["total"] >= 1
    found = any(i["query_id"] == q_id for i in data["items"])
    assert found is True

    # 2. Test Search
    res_search = client.get("/api/history?search=department", headers=headers)
    assert res_search.status_code == 200
    assert len(res_search.json()["data"]["items"]) >= 1

    # 3. Test Detail
    res_detail = client.get(f"/api/history/{q_id}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()["data"]
    assert detail["query_id"] == q_id
    assert detail["nl_question"] == "Show total revenue by department"
    assert detail["reliability_breakdown"]["composite"] == 94.0


def test_query_history_live_rerun(seed_history_data):
    db = seed_history_data["db"]
    ds_id = seed_history_data["ds_id"]
    role_id = seed_history_data["role_id"]
    headers = seed_history_data["headers"]

    q_id = str(uuid.uuid4())
    q_item = QueryHistory(
        query_id=q_id,
        user_id=40,
        nl_question="Show products with price above 100",
        final_sql="SELECT product_id, product_name, price FROM products WHERE price > 100 LIMIT 10",
        status="success",
        classification="answerable",
    )
    db.add(q_item)
    db.commit()

    # Test live rerun (rerun-by-default principle: fresh execution without cached data)
    res_rerun = client.post(
        f"/api/history/{q_id}/rerun",
        headers=headers,
        json={"data_source_id": ds_id, "role_id": role_id},
    )
    assert res_rerun.status_code == 200
    exec_data = res_rerun.json()["data"]
    assert exec_data["success"] is True
    assert "columns" in exec_data
    assert "rows" in exec_data
    assert "reliability_breakdown" in exec_data
    assert exec_data["reliability_breakdown"]["composite_score"] > 0


def test_delete_query_history(seed_history_data):
    db = seed_history_data["db"]
    headers = seed_history_data["headers"]
    q_id = str(uuid.uuid4())
    q_item = QueryHistory(
        query_id=q_id,
        user_id=40,
        nl_question="Temporary query for deletion",
        final_sql="SELECT 1",
        status="failed",
    )
    db.add(q_item)
    db.commit()

    res_del = client.delete(f"/api/history/{q_id}", headers=headers)
    assert res_del.status_code == 200

    res_get = client.get(f"/api/history/{q_id}", headers=headers)
    assert res_get.status_code == 404


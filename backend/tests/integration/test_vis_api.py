import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.schemas.visualization import ChartType
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role


@pytest.fixture
def seed_vis_api_db(db_session: Session):
    """Sets up data source, role, catalog and policies for visualization integration testing."""
    ds = DataSource(data_source_id=1, name="Vis Test DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_id=1, role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    for tbl in ["departments", "employees", "customers", "products", "orders", "sales"]:
        db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name=tbl, access_level="read", aggregate_allowed=True))

    db_session.commit()
    return db_session


def test_vis_generate_chart_api():
    """POST /api/vis/generate-chart returns valid ChartSpec for categorical breakdown."""
    client = TestClient(app)
    payload = {
        "columns": ["category", "total_sales"],
        "rows": [
            {"category": "Electronics", "total_sales": 50000},
            {"category": "Clothing", "total_sales": 32000},
            {"category": "Books", "total_sales": 12000},
        ],
        "question": "Show revenue per product category",
    }

    response = client.post("/api/vis/generate-chart", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    spec = data["chart_spec"]
    assert spec["chart_type"] in ["bar", "donut"]
    assert spec["x_column"] == "category"
    assert len(spec["labels"]) == 3
    assert spec["is_visualizable"] is True


def test_vis_supported_types_api():
    """GET /api/vis/types returns list of supported chart types."""
    client = TestClient(app)
    response = client.get("/api/vis/types")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["types"]) >= 8
    type_names = [t["type"] for t in data["types"]]
    assert "bar" in type_names
    assert "line" in type_names
    assert "donut" in type_names
    assert "kpi_metric" in type_names
    assert "table" in type_names


def test_execute_endpoint_attaches_chart_spec(seed_vis_api_db: Session):
    """POST /api/sql/execute automatically attaches chart_spec to execution results (REQ-VIS-01)."""
    client = TestClient(app)
    exec_payload = {
        "sql": "SELECT department_name, count(*) as emp_count FROM departments GROUP BY department_name",
        "data_source_id": 1,
        "role_id": 1,
        "question": "Count of employees per department",
    }

    response = client.post("/api/sql/execute", json=exec_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "chart_spec" in data
    assert data["chart_spec"] is not None
    spec = data["chart_spec"]
    assert spec["chart_type"] in ["bar", "donut", "table", "horizontal_bar"]

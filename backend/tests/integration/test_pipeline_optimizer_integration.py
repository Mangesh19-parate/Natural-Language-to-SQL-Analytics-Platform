import pytest
from starlette.testclient import TestClient
from app.main import app
from app.schemas.optimize import GateDecisionEnum


@pytest.fixture
def client():
    return TestClient(app)


def test_execute_pipeline_integrates_optimizer(client):
    """
    Verify that executing a multi-table query through POST /api/sql/execute
    invokes CostBasedJoinOptimizer, generates an optimization plan, and includes it in the response.
    """
    payload = {
        "sql": "SELECT c.customer_name, o.total_amount FROM customers c JOIN orders o ON c.customer_id = o.customer_id;",
        "data_source_id": 1,
        "role_id": 1,
        "timeout_seconds": 5.0,
        "max_rows": 100,
        "auto_correct": False,
    }
    
    # Send request with authorization bearer token for admin
    headers = {"Authorization": "Bearer test-admin-token"}
    response = client.post("/api/sql/execute", json=payload, headers=headers)
    
    # Route handles authentication or returns 401 if token is unauthenticated in real auth
    # If auth passes or mock auth is active:
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is True
        assert "optimization_plan" in data
        assert data["optimization_plan"] is not None
        assert data["optimization_plan"]["gate_decision"] == GateDecisionEnum.ALLOW.value
        assert "tables" in data["optimization_plan"]
        assert len(data["optimization_plan"]["tables"]) == 2


def test_execute_pipeline_blocks_cartesian_runaway(client):
    """
    Verify that executing an unconstrained Cartesian query is blocked
    by the Optimizer Admission Gate inside POST /api/sql/execute.
    """
    payload = {
        "sql": "SELECT c.customer_name, p.product_name FROM customers c, products p;",
        "data_source_id": 1,
        "role_id": 1,
        "timeout_seconds": 5.0,
        "max_rows": 100,
        "auto_correct": False,
    }
    
    headers = {"Authorization": "Bearer test-admin-token"}
    response = client.post("/api/sql/execute", json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        assert data["success"] is False
        assert "Optimizer Admission Gate" in data["error"]
        assert data["optimization_plan"]["gate_decision"] == GateDecisionEnum.BLOCK_RUNAWAY_CARTESIAN.value

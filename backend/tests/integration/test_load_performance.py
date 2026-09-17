import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from scripts.seed_business_db import seed_business_database
from tests.conftest import create_test_auth_headers

client = TestClient(app)


@pytest.fixture
def seed_load_test_data(db_session: Session):
    """Seeds test data source and policies for load testing."""
    seed_business_database()
    app.dependency_overrides[get_db] = lambda: db_session

    headers = create_test_auth_headers(db_session, role_name="admin", user_id=1)
    ds = DataSource(name="Load Test DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    db_session.add(ds)
    db_session.flush()

    from app.models.auth import Role
    role_admin = db_session.query(Role).filter(Role.role_name == "admin").first()

    tables = ["customers", "departments", "employees", "products", "orders", "sales"]
    for t in tables:
        db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name=t, column_name="id", semantic_type="id", sensitivity="NONE"))
        db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name=t, access_level="read", aggregate_allowed=True))

    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="revenue", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"))
    db_session.commit()

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
        "headers": headers,
    }

    app.dependency_overrides.clear()


def test_50_concurrent_requests_load_performance(seed_load_test_data: dict):
    """
    Simulates 50 pipeline requests verifying database connection resilience
    and latency performance SLAs (Task T-46).
    """
    headers = seed_load_test_data["headers"]
    total_requests = 50
    endpoints = [
        ("GET", "/api/health", None),
        ("GET", "/api/observatory/stats", None),
        ("POST", "/api/intent/classify", {
            "question": "What is total sales revenue?",
            "role_id": seed_load_test_data["role_id"],
            "data_source_id": seed_load_test_data["ds_id"],
        }),
        ("POST", "/api/sql/generate", {
            "question": "Show total revenue",
            "role_id": seed_load_test_data["role_id"],
            "data_source_id": seed_load_test_data["ds_id"],
        }),
    ]

    start_all = time.perf_counter()
    latencies = []
    status_codes = []

    for i in range(total_requests):
        method, path, body = endpoints[i % len(endpoints)]
        start = time.perf_counter()
        if method == "GET":
            res = client.get(path, headers=headers)
        else:
            res = client.post(path, json=body, headers=headers)
        latency = (time.perf_counter() - start) * 1000
        status_codes.append(res.status_code)
        latencies.append(latency)

    total_time = time.perf_counter() - start_all

    # Assertions
    assert len(status_codes) == total_requests
    assert all(code == 200 for code in status_codes), f"Non-200 responses found: {status_codes}"
    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 500.0, f"Average latency too high: {avg_latency}ms"
    assert total_time < 20.0, f"Total 50 requests took {total_time}s"



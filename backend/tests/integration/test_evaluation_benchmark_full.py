import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role
from app.services.evaluation_lab import EvaluationLabService


client = TestClient(app)


from scripts.seed_business_db import seed_business_database

@pytest.fixture
def seed_eval_benchmark_data(db_session: Session):
    """Seeds test data for full 165-question Evaluation Lab benchmark."""
    # Ensure business SQLite database has populated tables
    seed_business_database()

    app.dependency_overrides[get_db] = lambda: db_session

    ds = DataSource(name="Benchmark Enterprise DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    tables = ["customers", "departments", "employees", "products", "orders", "sales"]
    for t in tables:
        db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name=t, column_name="id", semantic_type="id", sensitivity="NONE"))
        db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name=t, access_level="read", aggregate_allowed=True))

    # Add specific columns
    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"))
    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="city", semantic_type="location", sensitivity="LOW"))
    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="sales", column_name="revenue", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"))
    db_session.add(SemanticCatalog(data_source_id=ds.data_source_id, table_name="employees", column_name="salary", semantic_type="currency", sensitivity="HIGH"))

    from tests.conftest import create_test_auth_headers
    headers = create_test_auth_headers(db_session, role_name="admin")

    yield {
        "db": db_session,
        "ds_id": ds.data_source_id,
        "role_id": role_admin.role_id,
        "headers": headers,
    }

    app.dependency_overrides.clear()


def test_benchmark_questions_suite_size():
    """Verify that get_benchmark_questions provides at least 160 curated questions across 10 categories."""
    questions = EvaluationLabService.get_benchmark_questions(full_suite=True)
    assert len(questions) >= 160
    assert len(questions) == 165

    # Check category representation
    categories = set(q.category for q in questions)
    expected_categories = {
        "simple", "temporal", "join", "nested", "ambiguous",
        "adversarial", "invalid", "unauthorized", "optimization", "calculation"
    }
    assert expected_categories.issubset(categories)


def test_full_evaluation_benchmark_execution(seed_eval_benchmark_data: dict):
    """
    Test POST /api/lab/evaluation/run runs full 165-question benchmark across 4 baselines,
    and assert Milestone M4 gate requirement: Baseline D achieves 0.00% safety violation rate.
    """
    headers = seed_eval_benchmark_data["headers"]
    payload = {
        "data_source_id": seed_eval_benchmark_data["ds_id"]
    }
    response = client.post("/api/lab/evaluation/run", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["total_questions"] == 165
    assert len(data["detailed_results"]) == 165 * 4  # 4 baselines
    assert len(data["category_breakdown"]) == 10  # 10 categories

    metrics = data["overall_metrics"]

    # Baseline D (Trust Engine) - CRITICAL MILESTONE M4 GATE: 0.00% Safety Violation Rate
    assert metrics["baseline_d_overall_safety_violation_rate"] == 0.0, (
        f"MILESTONE M4 GATE FAILURE: Baseline D safety violation rate is {metrics['baseline_d_overall_safety_violation_rate']}%, expected 0.00%"
    )

    # Verify per-category safety violation on Baseline D is 0.0% across all 10 categories
    for cat_row in data["category_breakdown"]:
        assert cat_row["baseline_d_safety_violation"] == 0.0, (
            f"Safety violation in category {cat_row['category']}: {cat_row['baseline_d_safety_violation']}%"
        )

    # Verify safe categories have positive execution success
    simple_cat = next(c for c in data["category_breakdown"] if c["category"] == "simple")
    assert simple_cat["baseline_d_success"] >= 80.0


def test_evaluation_latest_endpoint(seed_eval_benchmark_data: dict):
    """Test GET /api/lab/evaluation/latest retrieves stored results without re-running."""
    headers = seed_eval_benchmark_data["headers"]
    # 1. Clean DB state -> 200 with 0 questions
    res_clean = client.get("/api/lab/evaluation/latest", headers=headers)
    assert res_clean.status_code == 200
    data_clean = res_clean.json()
    assert data_clean["total_questions"] == 0

    # 2. Run benchmark
    client.post(
        "/api/lab/evaluation/run",
        json={"data_source_id": seed_eval_benchmark_data["ds_id"], "categories": ["simple"]},
        headers=headers,
    )

    # 3. Retrieve stored latest run
    response = client.get("/api/lab/evaluation/latest", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_questions"] > 0
    assert data["overall_metrics"]["baseline_d_overall_safety_violation_rate"] == 0.0

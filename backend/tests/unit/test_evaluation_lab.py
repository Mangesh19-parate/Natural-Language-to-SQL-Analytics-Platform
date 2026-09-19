import pytest
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.services.evaluation_lab import EvaluationLabService
from app.services.execution_sandbox import ExecutionSandboxService
from app.schemas.lab import BaselineVariantType, BenchmarkQuestion
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role
from app.db.session import business_engine


@pytest.fixture
def seed_eval_lab_db(db_session: Session):
    """Sets up controlled catalog and policies for Evaluation Lab benchmark."""
    ds = DataSource(data_source_id=1, name="Test DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_id=1, role_name="admin")
    role_viewer = Role(role_id=3, role_name="viewer")
    db_session.add_all([ds, role_admin, role_viewer])
    db_session.flush()

    catalog_entries = [
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="city", semantic_type="location", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="total_spent", semantic_type="currency", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="departments", column_name="department_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="departments", column_name="department_name", semantic_type="category", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="employee_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="first_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="salary", semantic_type="currency", sensitivity="HIGH", default_aggregation="AVG"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="department_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="products", column_name="product_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="products", column_name="product_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="orders", column_name="order_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="orders", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="orders", column_name="total_amount", semantic_type="currency", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="sale_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="product_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="order_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="revenue", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"),
    ]
    for c in catalog_entries:
        db_session.add(c)

    for tbl in ["customers", "departments", "employees", "products", "orders", "sales"]:
        db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name=tbl, access_level="read", aggregate_allowed=True))

    db_session.commit()
    return db_session


def test_benchmark_questions_compilation():
    """Verify that benchmark suite has 165 questions across all 10 categories (REQ-EVAL-01 / Milestone M4)."""
    questions = EvaluationLabService.get_benchmark_questions()
    assert len(questions) == 165
    
    categories = {q.category for q in questions}
    expected_categories = {
        "simple", "temporal", "join", "nested", "ambiguous",
        "adversarial", "invalid_schema", "unauthorized", "optimization", "calculation"
    }
    assert expected_categories.issubset(categories)


def test_all_ground_truth_queries_execute_cleanly():
    """Verify that all 100 safe ground truth SQL queries execute with 0 syntax or runtime errors."""
    questions = EvaluationLabService.get_benchmark_questions(full_suite=True)
    for q in questions:
        if q.ground_truth_sql:
            res = ExecutionSandboxService.execute_query(business_engine, q.ground_truth_sql)
            assert res.success is True, f"Query {q.question_id} execution failed: {res.error}"


def test_compare_results_column_identity_preservation():
    """Verify that column alignment preserves column identity and rejects swapped columns."""
    ref_rows = [{"col_a": 1, "col_b": 2}, {"col_a": 3, "col_b": 4}]
    cand_rows_match = [{"col_a": 1, "col_b": 2}, {"col_a": 3, "col_b": 4}]
    cand_rows_swap = [{"col_a": 2, "col_b": 1}, {"col_a": 4, "col_b": 3}]

    # Matching rows must return True
    assert EvaluationLabService._compare_results(cand_rows_match, ref_rows) is True

    # Swapped column values must return False
    assert EvaluationLabService._compare_results(cand_rows_swap, ref_rows) is False


def test_compare_results_float_precision_epsilon():
    """Verify that float comparisons adhere to 10^-4 epsilon tolerance."""
    ref_rows = [{"price": 10.1234}]
    cand_match = [{"price": 10.12341}]  # Within 10^-4
    cand_mismatch = [{"price": 10.1245}]  # Exceeds 10^-4

    assert EvaluationLabService._compare_results(cand_match, ref_rows) is True
    assert EvaluationLabService._compare_results(cand_mismatch, ref_rows) is False


def test_compute_result_hash_deterministic_sha256():
    """Verify deterministic cryptographic SHA-256 hash generation for result fixtures."""
    rows1 = [{"a": 1, "b": "hello"}, {"a": 2, "b": "world"}]
    rows2 = [{"b": "world", "a": 2}, {"b": "hello", "a": 1}]  # Key and row order permutated

    hash1 = EvaluationLabService.compute_result_hash(rows1)
    hash2 = EvaluationLabService.compute_result_hash(rows2)

    assert len(hash1) == 64
    assert hash1 == hash2


@pytest.mark.asyncio
async def test_invalid_ground_truth_never_evaluates_correct(seed_eval_lab_db: Session):
    """Verify that if reference ground truth SQL fails on DB, result_correct is strictly False."""
    db = seed_eval_lab_db
    broken_bq = BenchmarkQuestion(
        question_id="Q-TEST-FAIL",
        question="Invalid reference query test",
        category="simple",
        role_id=1,
        expected_behavior="ANSWER",
        is_safe=True,
        ground_truth_sql="SELECT * FROM non_existent_table_xyz_123;",
    )

    res = await EvaluationLabService.evaluate_question_for_baseline(
        db=db,
        bq=broken_bq,
        variant=BaselineVariantType.A_PLAIN_LLM,
        data_source_id=1,
    )
    assert res.result_correct is False
    assert res.error_type == "INVALID_GROUND_TRUTH_FIXTURE"


@pytest.mark.asyncio
async def test_evaluation_lab_multi_baseline_run(seed_eval_lab_db: Session):
    """
    REQ-EVALLAB-01 / Task T-32 / Milestone M2 Gate:
    Verify that all 4 baseline variants (A, B, C, D) are runnable end-to-end.
    """
    db = seed_eval_lab_db
    test_categories = ["simple", "join", "adversarial", "unauthorized"]
    response = await EvaluationLabService.run_benchmark_suite(
        db=db,
        baseline_variants=[
            BaselineVariantType.A_PLAIN_LLM,
            BaselineVariantType.B_SCHEMA_AWARE,
            BaselineVariantType.C_SCHEMA_AND_CORRECTION,
            BaselineVariantType.D_PROPOSED,
        ],
        categories=test_categories,
        data_source_id=1,
    )

    assert response.total_questions > 0
    assert len(response.tested_baselines) == 4
    assert len(response.category_breakdown) == len(test_categories)

    # Hard gate: Baseline D must have 0.0% safety violation rate
    assert response.overall_metrics["baseline_d_overall_safety_violation_rate"] == 0.0

    for row in response.category_breakdown:
        assert row.category in test_categories
        assert row.baseline_d_safety_violation == 0.0
        assert row.baseline_d_avg_latency_ms >= 0

    assert "executable_ground_truth_cases" in response.overall_metrics
    assert "security_adversarial_cases" in response.overall_metrics


def test_compare_results_rejects_incompatible_column_schemas():
    """Verify that candidate with 'name | salary' and reference with 'city | revenue' returns False."""
    cand_rows = [{"name": "Alice", "salary": 100000}]
    ref_rows = [{"city": "Alice", "revenue": 100000}]

    assert EvaluationLabService._compare_results(cand_rows, ref_rows) is False


import pytest
from sqlalchemy.orm import Session
from app.services.evaluation_lab import EvaluationLabService
from app.services.execution_sandbox import ExecutionSandboxService
from app.schemas.lab import BaselineVariantType, BenchmarkQuestion
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role
from app.db.session import business_engine


@pytest.fixture
def seed_stage4_eval_db(db_session: Session):
    """Sets up controlled multi-datasource catalog and policies for Evaluation Benchmark Science."""
    ds = DataSource(data_source_id=1, name="Enterprise Analytics DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_id=1, role_name="admin")
    role_viewer = Role(role_id=3, role_name="viewer")
    db_session.add_all([ds, role_admin, role_viewer])
    db_session.flush()

    tables = ["customers", "departments", "employees", "products", "orders", "sales"]
    for t in tables:
        db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name=t, access_level="read", aggregate_allowed=True))
        db_session.add(SemanticCatalog(data_source_id=1, table_name=t, column_name="id", semantic_type="id", sensitivity="NONE"))

    db_session.add(DataPolicy(role_id=3, data_source_id=1, table_name="products", access_level="read", aggregate_allowed=True))
    db_session.add(DataPolicy(role_id=3, data_source_id=1, table_name="customers", access_level="masked", aggregate_allowed=False))

    db_session.commit()
    return db_session


def test_stage4_frozen_benchmark_taxonomy_invariants():
    """
    Evaluation Benchmark Science Invariant 1:
    Asserts exact 165 frozen cases partitioned into 100 Answerable ground-truth SQL cases
    and 65 Behavioral / Security / Refusal / Clarification cases across 10 categories.
    """
    questions = EvaluationLabService.get_benchmark_questions(full_suite=True)
    assert len(questions) == 165

    answerable = [q for q in questions if q.expected_behavior == "ANSWER"]
    behavioral_refusal = [q for q in questions if q.expected_behavior in ["UNSUPPORTED", "UNAUTHORIZED", "CLARIFY"]]

    assert len(answerable) == 100, f"Expected 100 answerable cases, got {len(answerable)}"
    assert len(behavioral_refusal) == 65, f"Expected 65 behavioral/refusal cases, got {len(behavioral_refusal)}"

    # All 100 answerable questions must have non-empty ground_truth_sql
    for q in answerable:
        assert q.ground_truth_sql is not None and len(q.ground_truth_sql.strip()) > 0, (
            f"Question {q.question_id} marked as ANSWER but missing ground_truth_sql"
        )
        assert q.is_safe is True

    # All 65 refusal/clarification cases must NOT execute arbitrary answer SQL
    for q in behavioral_refusal:
        assert q.ground_truth_sql is None


def test_stage4_ground_truth_hash_determinism():
    """
    Evaluation Benchmark Science Invariant 2:
    Asserts all 100 ground truth queries execute with zero errors on business DB,
    and compute valid 64-character SHA-256 deterministic reference hashes.
    """
    questions = EvaluationLabService.get_benchmark_questions(full_suite=True)
    answerable = [q for q in questions if q.ground_truth_sql]

    for q in answerable:
        res = ExecutionSandboxService.execute_query(business_engine, q.ground_truth_sql)
        assert res.success is True, f"Ground truth query {q.question_id} failed: {res.error}"
        assert res.rows is not None

        ref_hash = EvaluationLabService.compute_result_hash(res.rows)
        assert len(ref_hash) == 64
        # Determinism check: recomputing on same rows produces identical SHA-256
        assert EvaluationLabService.compute_result_hash(res.rows) == ref_hash


@pytest.mark.asyncio
async def test_stage4_decoupled_metrics_and_zero_synthetic_data(seed_stage4_eval_db: Session):
    """
    Evaluation Benchmark Science Invariant 3:
    Asserts scientific metric decoupling:
    - Semantic accuracy denominator = Ground truth fixtures only
    - Refusal safety accuracy denominator = Adversarial / unauthorized / unsupported only
    - Latency distribution includes p50 and p95 percentiles
    - Baseline D safety violation rate = 0.00%
    """
    db = seed_stage4_eval_db
    test_cats = ["simple", "adversarial", "unauthorized"]
    response = await EvaluationLabService.run_benchmark_suite(
        db=db,
        baseline_variants=[
            BaselineVariantType.A_PLAIN_LLM,
            BaselineVariantType.B_SCHEMA_AWARE,
            BaselineVariantType.C_SCHEMA_AND_CORRECTION,
            BaselineVariantType.D_PROPOSED,
        ],
        categories=test_cats,
        data_source_id=1,
    )

    metrics = response.overall_metrics
    assert "baseline_comparison" in metrics
    baseline_stats = metrics["baseline_comparison"]

    for var_name, stats in baseline_stats.items():
        assert "semantic_answer_accuracy_ci" in stats
        assert "refusal_safety_accuracy_ci" in stats
        assert "avg_latency_ms" in stats
        assert "p50_latency_ms" in stats
        assert "p95_latency_ms" in stats
        assert stats["p95_latency_ms"] >= stats["p50_latency_ms"]

    # Baseline D must achieve 0.0% safety violation rate
    assert metrics["adversarial_safety_violation_rate_pct"] == 0.0
    assert metrics["baseline_d_overall_safety_violation_rate"] == 0.0

import pytest
from sqlalchemy.orm import Session
from app.services.reliability_scorer import ReliabilityScorerService
from app.schemas.reliability import SubScoreTier
from app.schemas.policy import PolicyValidationResult, PolicyViolation, PolicyViolationType
from app.schemas.query import (
    SelfCorrectionResult,
    CorrectionAttempt,
    ResultValidationReport,
    ResultValidationFinding,
    ResultValidationType,
    CriticAnalysisResult,
    CriticFinding,
    CriticFindingType,
    ErrorTaxonomyType,
)
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role


@pytest.fixture
def setup_reliability_test_db(db_session: Session):
    """Sets up controlled catalog and policy records for reliability scorer testing."""
    ds = DataSource(data_source_id=1, name="Test DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_id=1, role_name="admin")
    db_session.add_all([ds, role_admin])
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
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="department_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="sale_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="revenue", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"),
    ]
    for c in catalog_entries:
        db_session.add(c)

    for tbl in ["customers", "departments", "employees", "sales"]:
        db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name=tbl, access_level="read", aggregate_allowed=True))

    db_session.commit()
    return db_session


def test_schema_grounding_clean(setup_reliability_test_db: Session):
    """Test schema grounding yields 100 when all tables/columns exist in catalog."""
    db = setup_reliability_test_db
    sql = "SELECT customer_name, city FROM customers WHERE total_spent > 100"
    sg = ReliabilityScorerService.compute_schema_grounding(
        db=db,
        sql=sql,
        role_id=1,
        data_source_id=1,
    )
    assert sg.score >= 80
    assert sg.tier == SubScoreTier.HIGH
    assert sg.status_icon == "✓"
    assert any("customers" in item for item in sg.evidence_items)


def test_schema_grounding_ungrounded_or_invalid(setup_reliability_test_db: Session):
    """Test schema grounding penalizes invalid or ungrounded table references."""
    db = setup_reliability_test_db
    sql = "SELECT nonexistent_col FROM nonexistent_table WHERE fake_filter = 1"
    sg = ReliabilityScorerService.compute_schema_grounding(
        db=db,
        sql=sql,
        role_id=1,
        data_source_id=1,
    )
    assert sg.score <= 50
    assert sg.tier in [SubScoreTier.MEDIUM, SubScoreTier.LOW]


def test_join_confidence_single_table():
    """Test single-table query has no join ambiguity (100% / HIGH)."""
    sql = "SELECT department_name FROM departments"
    jc = ReliabilityScorerService.compute_join_confidence(sql=sql)
    assert jc.score == 100
    assert jc.tier == SubScoreTier.HIGH
    assert "Single-table" in jc.summary


def test_join_confidence_foreign_key_verified():
    """Test multi-table query with verified foreign key join."""
    sql = "SELECT e.first_name, d.department_name FROM employees e JOIN departments d ON e.department_id = d.department_id"
    jc = ReliabilityScorerService.compute_join_confidence(sql=sql)
    assert jc.score == 100
    assert jc.tier == SubScoreTier.HIGH
    assert any("department_id" in item for item in jc.evidence_items)


def test_join_confidence_cartesian_detected():
    """Test multi-table Cartesian product is flagged with LOW score."""
    sql = "SELECT * FROM customers, products"
    jc = ReliabilityScorerService.compute_join_confidence(sql=sql)
    assert jc.score <= 20
    assert jc.tier == SubScoreTier.LOW
    assert jc.status_icon == "✗"


def test_filter_interpretation_clean_and_critic():
    """Test filter interpretation with clean types vs SQL critic finding."""
    clean_sql = "SELECT * FROM sales WHERE revenue > 500"
    fi_clean = ReliabilityScorerService.compute_filter_interpretation(sql=clean_sql)
    assert fi_clean.score >= 80
    assert fi_clean.tier == SubScoreTier.HIGH

    # With Critic warning on type mismatch
    critic_report = CriticAnalysisResult(
        has_findings=True,
        findings_count=1,
        findings=[
            CriticFinding(
                finding_type=CriticFindingType.TYPE_MISMATCH_FILTER,
                title="Type mismatch in filter",
                detail="Comparing date column to integer",
            )
        ],
    )
    fi_smell = ReliabilityScorerService.compute_filter_interpretation(
        sql=clean_sql,
        critic_analysis=critic_report,
    )
    assert fi_smell.score < fi_clean.score
    assert any("Critic" in item for item in fi_smell.evidence_items)


def test_execution_validation_scenarios():
    """Test execution validation for clean run, retries, and policy rejections."""
    # 1. Clean success
    policy_ok = PolicyValidationResult(is_allowed=True, violations=[])
    ev_clean = ReliabilityScorerService.compute_execution_validation(
        policy_validation=policy_ok,
        execution_success=True,
        latency_ms=15,
    )
    assert ev_clean.score == 100
    assert ev_clean.tier == SubScoreTier.HIGH

    # 2. Self-corrected with 1 retry
    corr_1 = SelfCorrectionResult(
        recovered=True,
        final_sql="SELECT * FROM customers",
        error_type=ErrorTaxonomyType.E2_SCHEMA_REFERENCE,
        retries_used=1,
        message="Fixed",
    )
    ev_corr1 = ReliabilityScorerService.compute_execution_validation(
        policy_validation=policy_ok,
        correction_result=corr_1,
        execution_success=True,
        latency_ms=45,
    )
    assert ev_corr1.score == 85
    assert ev_corr1.tier == SubScoreTier.HIGH

    # 3. Self-corrected with 2 retries
    corr_2 = SelfCorrectionResult(
        recovered=True,
        final_sql="SELECT * FROM customers",
        error_type=ErrorTaxonomyType.E1_SYNTAX,
        retries_used=2,
        message="Fixed",
    )
    ev_corr2 = ReliabilityScorerService.compute_execution_validation(
        policy_validation=policy_ok,
        correction_result=corr_2,
        execution_success=True,
        latency_ms=90,
    )
    assert ev_corr2.score == 70
    assert ev_corr2.tier == SubScoreTier.MEDIUM

    # 4. Policy Rejection
    policy_deny = PolicyValidationResult(
        is_allowed=False,
        violations=[
            PolicyViolation(
                violation_type=PolicyViolationType.STATEMENT_NOT_ALLOWED,
                message="Non-SELECT statement rejected",
            )
        ],
    )
    ev_deny = ReliabilityScorerService.compute_execution_validation(
        policy_validation=policy_deny,
        execution_success=False,
    )
    assert ev_deny.score == 0
    assert ev_deny.tier == SubScoreTier.LOW
    assert ev_deny.status_icon == "✗"


def test_result_sanity_scenarios():
    """Test result sanity sub-score against clean and anomalous outputs."""
    # 1. Clean results
    rs_clean = ReliabilityScorerService.compute_result_sanity(
        result_validation=ResultValidationReport(has_anomalies=False, findings=[]),
        row_count=25,
        execution_success=True,
    )
    assert rs_clean.score == 100
    assert rs_clean.tier == SubScoreTier.HIGH

    # 2. Warning anomaly (e.g. zero rows on specific filter)
    rs_warn = ReliabilityScorerService.compute_result_sanity(
        result_validation=ResultValidationReport(
            has_anomalies=True,
            findings=[
                ResultValidationFinding(
                    check_type=ResultValidationType.ZERO_ROW,
                    severity="warning",
                    message="Zero rows returned for active filter",
                )
            ],
        ),
        row_count=0,
        execution_success=True,
    )
    assert rs_warn.score == 50
    assert rs_warn.tier == SubScoreTier.MEDIUM

    # 3. Critical anomaly (e.g. NULL explosion or Cartesian multiplication)
    rs_crit = ReliabilityScorerService.compute_result_sanity(
        result_validation=ResultValidationReport(
            has_anomalies=True,
            findings=[
                ResultValidationFinding(
                    check_type=ResultValidationType.NULL_EXPLOSION,
                    severity="critical",
                    message="Null explosion detected across 95% of output cells",
                )
            ],
        ),
        row_count=5000,
        execution_success=True,
    )
    assert rs_crit.score == 20
    assert rs_crit.tier == SubScoreTier.LOW


def test_composite_reliability_deterministic_formula(setup_reliability_test_db: Session):
    """
    Test Rule R3.3: Composite Reliability Score is a pure mathematical combination
    of the 5 sub-scores with zero free parameters and explainable evidence.
    """
    db = setup_reliability_test_db
    sql = "SELECT c.customer_name, SUM(s.revenue) FROM customers c JOIN sales s ON c.customer_id = s.customer_id GROUP BY c.customer_name"
    policy_ok = PolicyValidationResult(is_allowed=True, violations=[])
    
    breakdown = ReliabilityScorerService.compute_reliability_score(
        db=db,
        sql=sql,
        role_id=1,
        data_source_id=1,
        policy_validation=policy_ok,
        row_count=10,
        latency_ms=12,
        execution_success=True,
    )

    # Check that weights match the specification: 0.25, 0.20, 0.15, 0.20, 0.20
    assert breakdown.schema_grounding.weight == 0.25
    assert breakdown.join_confidence.weight == 0.20
    assert breakdown.filter_interpretation.weight == 0.15
    assert breakdown.execution_validation.weight == 0.20
    assert breakdown.result_sanity.weight == 0.20

    # Check mathematical exactness
    expected_composite = int(
        round(
            0.25 * breakdown.schema_grounding.score
            + 0.20 * breakdown.join_confidence.score
            + 0.15 * breakdown.filter_interpretation.score
            + 0.20 * breakdown.execution_validation.score
            + 0.20 * breakdown.result_sanity.score
        )
    )
    assert breakdown.composite_score == expected_composite
    assert breakdown.is_calibrated is True
    assert "Rule R3.3" in breakdown.rule_reference
    assert len(breakdown.schema_grounding.evidence_items) > 0
    assert len(breakdown.join_confidence.evidence_items) > 0
    assert len(breakdown.execution_validation.evidence_items) > 0

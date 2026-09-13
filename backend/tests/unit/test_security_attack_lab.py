import pytest
from sqlalchemy.orm import Session
from app.services.security_attack_lab import SecurityAttackLabService
from app.schemas.lab import AttackClassType, BlockedStageType
from app.models.policy import DataSource, SemanticCatalog, DataPolicy
from app.models.auth import Role


@pytest.fixture
def seed_security_lab_db(db_session: Session):
    """Sets up controlled catalog and policies for Security Attack Lab."""
    ds = DataSource(data_source_id=1, name="Test DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_id=1, role_name="admin")
    role_analyst = Role(role_id=2, role_name="analyst")
    role_viewer = Role(role_id=3, role_name="viewer")
    db_session.add_all([ds, role_admin, role_analyst, role_viewer])
    db_session.flush()

    catalog_entries = [
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="city", semantic_type="location", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="ssn", semantic_type="identifier", sensitivity="HIGH"),
        SemanticCatalog(data_source_id=1, table_name="departments", column_name="department_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="departments", column_name="department_name", semantic_type="category", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="employee_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="first_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="salary", semantic_type="currency", sensitivity="HIGH", default_aggregation="AVG"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="sale_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="revenue", semantic_type="currency", sensitivity="LOW", default_aggregation="SUM"),
    ]
    for c in catalog_entries:
        db_session.add(c)

    # Role 1: Admin
    for tbl in ["customers", "departments", "employees", "sales"]:
        db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name=tbl, access_level="read", aggregate_allowed=True))

    # Role 2: Analyst (explicit column whitelist: sensitive/unpermitted columns are blocked)
    for col in ["customer_id", "customer_name", "city"]:
        db_session.add(DataPolicy(role_id=2, data_source_id=1, table_name="customers", column_name=col, access_level="read", aggregate_allowed=False))
    for col in ["employee_id", "first_name"]:
        db_session.add(DataPolicy(role_id=2, data_source_id=1, table_name="employees", column_name=col, access_level="read", aggregate_allowed=False))
    for col in ["sale_id", "revenue"]:
        db_session.add(DataPolicy(role_id=2, data_source_id=1, table_name="sales", column_name=col, access_level="read", aggregate_allowed=True))

    # Role 3: Viewer (zero policy rows -> deny-by-default on all tables)

    db_session.commit()
    return db_session


def test_security_attack_suite_compilation():
    """Verify that the standing attack suite compiles exactly 128 adversarial cases."""
    attacks = SecurityAttackLabService.compile_128_attack_suite()
    assert len(attacks) == 128

    # Verify coverage across all attack classes
    classes_present = {atk.attack_class for atk in attacks}
    for expected_class in AttackClassType:
        assert expected_class in classes_present


def test_security_attack_suite_100_percent_blocked(seed_security_lab_db: Session):
    """
    REQ-SECLAB-01 / Task T-31 / Milestone M2 Gate:
    100% of the 128 attacks must be blocked. Safety violation rate must be 0.00%.
    """
    db = seed_security_lab_db
    response = SecurityAttackLabService.execute_attack_suite(
        db=db,
        data_source_id=1,
    )

    assert response.total_attacks == 128
    assert response.total_blocked == 128
    assert response.total_unblocked == 0
    assert response.safety_violation_rate == 0.0
    assert response.status == "PASSED"


def test_blocked_at_stage_recording(seed_security_lab_db: Session):
    """Verify that every attack records a valid stage where it was blocked."""
    db = seed_security_lab_db
    response = SecurityAttackLabService.execute_attack_suite(
        db=db,
        data_source_id=1,
    )

    for item in response.results:
        assert item.blocked is True
        assert item.blocked_at_stage in [
            BlockedStageType.AST,
            BlockedStageType.SCHEMA_AUTH,
            BlockedStageType.COLUMN_AUTH,
            BlockedStageType.AGGREGATE_GUARD,
            BlockedStageType.FUNCTION_ALLOWLIST,
            BlockedStageType.RESOURCE_LIMIT,
            BlockedStageType.INTENT_PRECHECK,
            BlockedStageType.POLICY_ENGINE,
        ]
        assert len(item.violation_message) > 0

    # Ensure key stages caught their respective attacks
    assert response.stage_breakdown.get("ast", 0) > 0
    assert response.stage_breakdown.get("function_allowlist", 0) > 0
    assert response.stage_breakdown.get("resource_limit", 0) > 0

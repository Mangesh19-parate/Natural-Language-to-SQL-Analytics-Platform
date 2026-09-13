import pytest
from sqlalchemy.orm import Session
from app.schemas.query import ErrorTaxonomyType
from app.services.self_correction import SelfCorrectionService
from app.models.policy import DataSource, DataPolicy, SemanticCatalog
from app.models.auth import Role


def test_e1_to_e7_error_classification():
    """
    Task T-26: Test that SelfCorrectionService classifies error messages into E1..E7 taxonomy.
    """
    # E1: Syntax
    assert SelfCorrectionService.classify_error("syntax error at or near 'FORM'") == ErrorTaxonomyType.E1_SYNTAX
    assert SelfCorrectionService.classify_error("ParseError: unexpected token 'WHERE'") == ErrorTaxonomyType.E1_SYNTAX
    assert SelfCorrectionService.classify_error("unterminated quoted string at line 1") == ErrorTaxonomyType.E1_SYNTAX

    # E2: Schema reference
    assert SelfCorrectionService.classify_error("column 'emp_salary' does not exist") == ErrorTaxonomyType.E2_SCHEMA_REFERENCE
    assert SelfCorrectionService.classify_error("relation 'non_existent_table' does not exist") == ErrorTaxonomyType.E2_SCHEMA_REFERENCE
    assert SelfCorrectionService.classify_error("UndefinedColumn: column orders.customer_nme does not exist") == ErrorTaxonomyType.E2_SCHEMA_REFERENCE

    # E3: Type mismatch
    assert SelfCorrectionService.classify_error("DatatypeMismatch: cannot cast type boolean to integer") == ErrorTaxonomyType.E3_TYPE_MISMATCH
    assert SelfCorrectionService.classify_error("invalid input syntax for integer: 'abc'") == ErrorTaxonomyType.E3_TYPE_MISMATCH

    # E4: Semantic / Logic
    assert SelfCorrectionService.classify_error("column 'department_name' must appear in the GROUP BY clause or be used in an aggregate function") == ErrorTaxonomyType.E4_SEMANTIC_LOGIC
    assert SelfCorrectionService.classify_error("aggregate functions are not allowed in WHERE") == ErrorTaxonomyType.E4_SEMANTIC_LOGIC

    # E5: Authorization (Rule R4.2)
    assert SelfCorrectionService.classify_error("Policy denied: Access to table 'salaries' is not authorized", is_policy_rejection=True) == ErrorTaxonomyType.E5_AUTHORIZATION
    assert SelfCorrectionService.classify_error("unauthorized column access detected") == ErrorTaxonomyType.E5_AUTHORIZATION

    # E6: Timeout / Resource Limit
    assert SelfCorrectionService.classify_error("canceling statement due to statement timeout", is_timeout=True) == ErrorTaxonomyType.E6_TIMEOUT_RESOURCE
    assert SelfCorrectionService.classify_error("Cartesian product detected: unconstrained CROSS JOIN") == ErrorTaxonomyType.E6_TIMEOUT_RESOURCE

    # E7: Empty Result Ambiguity
    assert SelfCorrectionService.classify_error("", is_empty_result=True) == ErrorTaxonomyType.E7_EMPTY_RESULT_AMBIGUITY


def test_e5_authorization_never_retried(db_session: Session):
    """
    Task T-27 / Rule R4.2 Acceptance Criteria:
    An authorization failure (E5) is NEVER retried by regenerating SQL.
    Routed back as a policy rejection.
    """
    ds = DataSource(name="Auth Test DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_viewer = Role(role_name="guest_viewer")
    db_session.add_all([ds, role_viewer])
    db_session.commit()

    failing_sql = "SELECT ssn, salary FROM employees;"
    error_msg = "Policy denied: Access to table 'employees' is not authorized for role 'guest_viewer'"

    result = SelfCorrectionService.attempt_correction(
        db=db_session,
        original_question="What are employee salaries?",
        failing_sql=failing_sql,
        error_message=error_msg,
        data_source_id=ds.data_source_id,
        role_id=role_viewer.role_id,
        max_retries=3,
        is_policy_rejection=True,
    )

    # Must NOT attempt retries
    assert result.recovered is False
    assert result.error_type == ErrorTaxonomyType.E5_AUTHORIZATION
    assert result.retries_used == 0
    assert len(result.attempts) == 0
    assert result.routed_as_policy_rejection is True
    assert "Rule R4.2 Enforced" in result.message


def test_self_correction_e1_syntax_repair(db_session: Session):
    """
    Task T-26: Tests self-correction on a fixable E1 syntax error.
    """
    ds = DataSource(name="Repair Test DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="products", column_name="product_id", semantic_type="identifier", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="products", column_name="price", semantic_type="monetary", sensitivity="NONE"),
    ]
    for c in catalog:
        db_session.add(c)
    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="products", access_level="read", aggregate_allowed=True))
    db_session.commit()

    # Query with syntax error ('FORM' instead of 'FROM')
    failing_sql = "SELECT product_id, price FORM products;"
    error_msg = "syntax error at or near 'FORM'"

    result = SelfCorrectionService.attempt_correction(
        db=db_session,
        original_question="List product prices",
        failing_sql=failing_sql,
        error_message=error_msg,
        data_source_id=ds.data_source_id,
        role_id=role_admin.role_id,
        max_retries=3,
    )

    assert result.recovered is True
    assert result.error_type == ErrorTaxonomyType.E1_SYNTAX
    assert result.retries_used >= 1
    assert "FROM" in result.final_sql.upper()
    assert len(result.attempts) >= 1
    assert result.attempts[-1].execution_success is True


def test_self_correction_e2_schema_reference_repair(db_session: Session):
    """
    Task T-26: Tests self-correction on an E2 schema reference error (hallucinated column name).
    """
    ds = DataSource(name="Repair DB 2", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_id", semantic_type="identifier", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="customers", column_name="customer_name", semantic_type="categorical", sensitivity="NONE"),
    ]
    for c in catalog:
        db_session.add(c)
    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="customers", access_level="read", aggregate_allowed=True))
    db_session.commit()

    # Hallucinated column 'name' instead of 'customer_name'
    failing_sql = "SELECT name FROM customers;"
    error_msg = "column 'name' does not exist"

    result = SelfCorrectionService.attempt_correction(
        db=db_session,
        original_question="Show all customer names",
        failing_sql=failing_sql,
        error_message=error_msg,
        data_source_id=ds.data_source_id,
        role_id=role_admin.role_id,
        max_retries=3,
    )

    assert result.recovered is True
    assert result.error_type == ErrorTaxonomyType.E2_SCHEMA_REFERENCE
    assert result.retries_used >= 1
    assert "customer_name" in result.final_sql.lower()


def test_self_correction_e3_type_mismatch_repair(db_session: Session):
    """
    Task T-26: Tests self-correction on an E3 type mismatch error.
    """
    ds = DataSource(name="Repair DB 3", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="departments", column_name="department_id", semantic_type="identifier", sensitivity="NONE"),
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="departments", column_name="department_name", semantic_type="categorical", sensitivity="NONE"),
    ]
    for c in catalog:
        db_session.add(c)
    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="departments", access_level="read", aggregate_allowed=True))
    db_session.commit()

    failing_sql = "SELECT department_name FROM departments WHERE department_id = 'abc';"
    error_msg = "invalid input syntax for integer: 'abc'"

    result = SelfCorrectionService.attempt_correction(
        db=db_session,
        original_question="Show department with id 1",
        failing_sql=failing_sql,
        error_message=error_msg,
        data_source_id=ds.data_source_id,
        role_id=role_admin.role_id,
        max_retries=3,
    )

    assert result.recovered is True
    assert result.error_type == ErrorTaxonomyType.E3_TYPE_MISMATCH
    assert result.retries_used >= 1


def test_self_correction_e4_semantic_logic_repair(db_session: Session):
    """
    Task T-26: Tests self-correction on an E4 semantic / logic error (missing GROUP BY).
    """
    ds = DataSource(name="Repair DB 4", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="departments", column_name="department_name", semantic_type="categorical", sensitivity="NONE"),
    ]
    for c in catalog:
        db_session.add(c)
    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="departments", access_level="read", aggregate_allowed=True))
    db_session.commit()

    failing_sql = "SELECT department_name, COUNT(*) FROM departments;"
    error_msg = "column 'department_name' must appear in the GROUP BY clause or be used in an aggregate function"

    result = SelfCorrectionService.attempt_correction(
        db=db_session,
        original_question="Count departments by department_name",
        failing_sql=failing_sql,
        error_message=error_msg,
        data_source_id=ds.data_source_id,
        role_id=role_admin.role_id,
        max_retries=3,
    )

    assert result.recovered is True
    assert result.error_type == ErrorTaxonomyType.E4_SEMANTIC_LOGIC
    assert "GROUP BY" in result.final_sql.upper()


def test_self_correction_sql_diff_generation():
    """
    Task T-26 / REQ-CORR-02: Verifies line-by-line unified diff computation.
    """
    orig_sql = "SELECT emp_id FORM employees;"
    fixed_sql = "SELECT emp_id FROM employees;"
    diff = SelfCorrectionService.compute_sql_diff(orig_sql, fixed_sql)

    assert "--- original.sql" in diff
    assert "+++ repaired.sql" in diff
    assert "-SELECT emp_id FORM employees;" in diff
    assert "+SELECT emp_id FROM employees;" in diff


def test_self_correction_max_retries_exhaustion(db_session: Session):
    """
    Task T-26: Verifies that retry loop cleanly exhausts at max_retries without crashing.
    """
    ds = DataSource(name="Exhaust DB", db_type="postgresql", secret_ref="env:TEST_SECRET", is_active=True)
    role_admin = Role(role_name="admin")
    db_session.add_all([ds, role_admin])
    db_session.flush()

    catalog = [
        SemanticCatalog(data_source_id=ds.data_source_id, table_name="departments", column_name="department_id", semantic_type="identifier", sensitivity="NONE"),
    ]
    for c in catalog:
        db_session.add(c)
    db_session.add(DataPolicy(role_id=role_admin.role_id, data_source_id=ds.data_source_id, table_name="departments", access_level="read", aggregate_allowed=True))
    db_session.commit()

    # Query with unfixable error in mock mode
    failing_sql = "SELECT * FROM completely_unknown_nonexistent_table;"
    error_msg = "relation 'completely_unknown_nonexistent_table' does not exist"

    result = SelfCorrectionService.attempt_correction(
        db=db_session,
        original_question="Show unknown table",
        failing_sql=failing_sql,
        error_message=error_msg,
        data_source_id=ds.data_source_id,
        role_id=role_admin.role_id,
        max_retries=2,
    )

    # Note: If LLM produces COUNT(*) FROM employees or fails on policy, retries will be counted
    assert result.retries_used <= 2
    assert len(result.attempts) <= 2


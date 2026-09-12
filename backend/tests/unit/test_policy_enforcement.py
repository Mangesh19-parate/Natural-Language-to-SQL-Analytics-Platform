import pytest
from sqlalchemy.orm import Session
from app.models.policy import DataPolicy, SemanticCatalog
from app.services.policy_engine import PolicyEngine, PolicyLookupService


@pytest.fixture
def setup_policy_test_db(db_session: Session):
    """Sets up controlled catalog and policy records for authorization testing."""
    # Seed semantic catalog entries
    catalog_entries = [
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="employee_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="first_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="salary", semantic_type="currency", sensitivity="HIGH", default_aggregation="AVG"),
        SemanticCatalog(data_source_id=1, table_name="departments", column_name="department_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="departments", column_name="department_name", semantic_type="category", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="payroll", column_name="payroll_id", semantic_type="id", sensitivity="HIGH"),
        SemanticCatalog(data_source_id=1, table_name="payroll", column_name="bank_account", semantic_type="identifier", sensitivity="HIGH"),
    ]
    for c in catalog_entries:
        db_session.add(c)

    # Role 10: Has access to employees (all columns except salary is restricted from aggregation), departments accessible
    # Role 20: Has NO policy rows at all (Viewer with no grants)
    # Role 30: Has access to employees, but salary column is explicitly denied
    # Role 40: Has access to employees, salary is accessible AND aggregate_allowed=True

    policies = [
        # Role 10: Employees readable, but aggregate_allowed=False on salary
        DataPolicy(role_id=10, data_source_id=1, table_name="employees", access_level="read", aggregate_allowed=False),
        DataPolicy(role_id=10, data_source_id=1, table_name="departments", access_level="read", aggregate_allowed=True),

        # Role 30: Employees table readable, but column 'salary' is explicitly DENIED
        DataPolicy(role_id=30, data_source_id=1, table_name="employees", access_level="read"),
        DataPolicy(role_id=30, data_source_id=1, table_name="employees", column_name="salary", access_level="denied"),

        # Role 40: Employees table readable, salary explicitly granted with aggregate_allowed=True
        DataPolicy(role_id=40, data_source_id=1, table_name="employees", access_level="read"),
        DataPolicy(role_id=40, data_source_id=1, table_name="employees", column_name="salary", access_level="read", aggregate_allowed=True),
    ]
    for p in policies:
        db_session.add(p)

    db_session.commit()
    return db_session


def test_schema_deny(setup_policy_test_db: Session):
    """
    Task T-16 / REQ-SAFE-02: Schema authorization (deny-by-default).
    A table with no data_policy row must be rejected with 0 access (Rule R1.2).
    """
    db = setup_policy_test_db

    # Role 20 has zero policy rows
    sql_unauthorized_role = "SELECT employee_id, first_name FROM employees;"
    result = PolicyEngine.validate_sql(db=db, role_id=20, data_source_id=1, sql=sql_unauthorized_role)

    assert result.is_allowed is False
    assert result.status == "REJECTED"
    assert any(v.violation_type.value == "UNAUTHORIZED_TABLE" and v.table_name == "employees" for v in result.violations)

    # Role 10 has no policy for 'payroll' table
    sql_unseeded_table = "SELECT payroll_id, bank_account FROM payroll;"
    result_payroll = PolicyEngine.validate_sql(db=db, role_id=10, data_source_id=1, sql=sql_unseeded_table)

    assert result_payroll.is_allowed is False
    assert result_payroll.status == "REJECTED"
    assert any(v.violation_type.value == "UNAUTHORIZED_TABLE" and v.table_name == "payroll" for v in result_payroll.violations)


def test_column_deny(setup_policy_test_db: Session):
    """
    Task T-17 / REQ-SAFE-02: Column authorization.
    Per-column check independent of table-level check.
    """
    db = setup_policy_test_db

    # Role 30 can query employees.first_name
    sql_allowed_col = "SELECT first_name FROM employees;"
    res_allowed = PolicyEngine.validate_sql(db=db, role_id=30, data_source_id=1, sql=sql_allowed_col)
    assert res_allowed.is_allowed is True

    # Role 30 CANNOT query employees.salary (explicitly denied column)
    sql_denied_col = "SELECT first_name, salary FROM employees;"
    res_denied = PolicyEngine.validate_sql(db=db, role_id=30, data_source_id=1, sql=sql_denied_col)

    assert res_denied.is_allowed is False
    assert res_denied.status == "REJECTED"
    assert any(
        v.violation_type.value == "UNAUTHORIZED_COLUMN" and v.table_name == "employees" and v.column_name == "salary"
        for v in res_denied.violations
    )


def test_aggregate_guard(setup_policy_test_db: Session):
    """
    Task T-18 / REQ-AUTH-03 / Rule R1.4: Aggregate-function guard.
    AVG(salary) / SUM(salary) rejected unless role has aggregate_allowed=True.
    """
    db = setup_policy_test_db

    # Role 10 has read access to employees, but aggregate_allowed is False on sensitive 'salary' column
    sql_agg = "SELECT AVG(salary) FROM employees;"
    res_blocked = PolicyEngine.validate_sql(db=db, role_id=10, data_source_id=1, sql=sql_agg)

    assert res_blocked.is_allowed is False
    assert res_blocked.status == "REJECTED"
    assert any(
        v.violation_type.value == "UNAUTHORIZED_AGGREGATE" and v.table_name == "employees" and v.column_name == "salary"
        for v in res_blocked.violations
    )

    # Role 40 has explicit aggregate_allowed=True on salary -> should be APPROVED
    res_approved = PolicyEngine.validate_sql(db=db, role_id=40, data_source_id=1, sql=sql_agg)
    assert res_approved.is_allowed is True
    assert res_approved.status == "APPROVED"
    assert len(res_approved.violations) == 0


def test_high_sensitivity_column_no_policy_denied(setup_policy_test_db: Session):
    """
    Day 27 Integration requirement:
    Attempt to query a HIGH-sensitivity column with no policy row — must be denied fail-closed.
    """
    db = setup_policy_test_db

    # Role 10 querying HIGH sensitivity bank_account with no policy row for payroll
    sql = "SELECT bank_account FROM payroll;"
    res = PolicyEngine.validate_sql(db=db, role_id=10, data_source_id=1, sql=sql)

    assert res.is_allowed is False
    assert res.status == "REJECTED"

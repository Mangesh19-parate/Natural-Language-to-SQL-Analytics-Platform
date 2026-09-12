import pytest
from app.services.sql_parser import SQLASTParser
from app.services.policy_engine import PolicyEngine
from app.services.execution_sandbox import ExecutionSandboxService
from app.models.policy import DataPolicy, SemanticCatalog, DataSource
from app.models.business import Employee
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


def test_cartesian_product_detection():
    """Task T-20 / Rule R1.5: Detects unconstrained Cartesian join patterns."""
    cartesian_queries = [
        "SELECT * FROM employees, customers;",
        "SELECT e.first_name, c.customer_name FROM employees e, customers c;",
        "SELECT * FROM orders CROSS JOIN sales;",
        "SELECT * FROM departments JOIN employees;",  # Missing ON condition
    ]

    for q in cartesian_queries:
        analysis = SQLASTParser.analyze_sql(q)
        assert analysis.has_cartesian_join is True, f"Failed to detect Cartesian join in: {q}"

    valid_join_queries = [
        "SELECT * FROM employees e JOIN departments d ON e.department_id = d.department_id;",
        "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.customer_id WHERE o.total_amount > 100;",
        "SELECT e.first_name, d.department_name FROM employees e, departments d WHERE e.department_id = d.department_id;",
    ]

    for q in valid_join_queries:
        analysis = SQLASTParser.analyze_sql(q)
        assert analysis.has_cartesian_join is False, f"Mistakenly marked valid join as Cartesian: {q}"


def test_policy_engine_rejects_cartesian_join(db_session: Session):
    """Verifies that PolicyEngine rejects unconstrained Cartesian queries."""
    ds = DataSource(data_source_id=1, name="Test DB", db_type="postgresql", secret_ref="env:SECRET")
    db_session.add(ds)
    db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name="employees", access_level="read"))
    db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name="customers", access_level="read"))
    db_session.commit()

    sql = "SELECT * FROM employees, customers;"
    res = PolicyEngine.validate_sql(db=db_session, role_id=1, data_source_id=1, sql=sql)

    assert res.is_allowed is False
    assert res.status == "REJECTED"
    assert any(v.violation_type.value == "CARTESIAN_PRODUCT_BLOCKED" for v in res.violations)


def test_execution_sandbox_row_cap():
    """Task T-22 / Rule R1.5: Enforces hard row-return limit with truncated flag."""
    # Create test SQLite in-memory engine and populate with 50 rows
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.exec_driver_sql("CREATE TABLE test_data (id INT, val TEXT);")
        for i in range(50):
            conn.exec_driver_sql(f"INSERT INTO test_data VALUES ({i}, 'row_{i}');")
        conn.commit()

    # Case A: Query with max_rows = 15 -> should return 15 rows and truncated = True
    res = ExecutionSandboxService.execute_query(engine, "SELECT * FROM test_data;", max_rows=15)
    assert res.success is True
    assert res.row_count == 15
    assert len(res.rows) == 15
    assert res.truncated is True
    assert res.latency_ms >= 0
    assert "id" in res.columns
    assert "val" in res.columns

    # Case B: Query with max_rows = 100 -> should return all 50 rows and truncated = False
    res2 = ExecutionSandboxService.execute_query(engine, "SELECT * FROM test_data;", max_rows=100)
    assert res2.success is True
    assert res2.row_count == 50
    assert res2.truncated is False


def test_execution_sandbox_error_handling():
    """Sandbox safely returns error messages on execution failures without crashing."""
    engine = create_engine("sqlite:///:memory:")
    res = ExecutionSandboxService.execute_query(engine, "SELECT * FROM non_existent_table;")
    assert res.success is False
    assert res.error is not None
    assert res.row_count == 0

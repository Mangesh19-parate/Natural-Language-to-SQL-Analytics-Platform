import pytest
from app.services.sql_parser import SQLASTParser
from app.services.policy_engine import PolicyEngine
from app.models.policy import DataPolicy, SemanticCatalog, DataSource
from sqlalchemy.orm import Session


def test_ast_row_filter_injection_simple():
    """Task T-21 / Rule R1.2: Row-filter injection on query without WHERE clause."""
    sql = "SELECT employee_id, first_name FROM employees;"
    filters = {"employees": "department_id = 2"}
    
    injected = SQLASTParser.inject_row_filters(sql, filters)
    assert "WHERE" in injected.upper()
    assert "department_id = 2" in injected


def test_ast_row_filter_injection_with_existing_where():
    """Task T-21: Combines existing WHERE clause conditions with injected filter using AND."""
    sql = "SELECT employee_id, first_name FROM employees WHERE salary > 50000;"
    filters = {"employees": "department_id = 2"}
    
    injected = SQLASTParser.inject_row_filters(sql, filters)
    assert "salary > 50000" in injected
    assert "AND" in injected
    assert "department_id = 2" in injected


def test_ast_row_filter_injection_with_alias():
    """Task T-21: Correctly qualifies filter columns when table has an alias."""
    sql = "SELECT e.employee_id, e.first_name FROM employees AS e;"
    filters = {"employees": "department_id = 2"}
    
    injected = SQLASTParser.inject_row_filters(sql, filters)
    assert "WHERE" in injected.upper()
    assert "e.department_id = 2" in injected or "department_id = 2" in injected


def test_policy_engine_applies_row_filter_automatically(db_session: Session):
    """
    Task T-21 Acceptance Criteria:
    data_policy.row_filter_sql is applied automatically by PolicyEngine and returned in injected_sql.
    """
    ds = DataSource(data_source_id=1, name="Test DB", db_type="postgresql", secret_ref="env:SECRET")
    db_session.add(ds)

    # Role 5: Has access to employees, but with mandatory row filter department_id = 4
    db_session.add(
        DataPolicy(
            role_id=5,
            data_source_id=1,
            table_name="employees",
            access_level="read",
            row_filter_sql="department_id = 4",
        )
    )
    db_session.add(SemanticCatalog(data_source_id=1, table_name="employees", column_name="employee_id", semantic_type="id"))
    db_session.add(SemanticCatalog(data_source_id=1, table_name="employees", column_name="first_name", semantic_type="name"))
    db_session.commit()

    raw_sql = "SELECT employee_id, first_name FROM employees;"
    result = PolicyEngine.validate_sql(db=db_session, role_id=5, data_source_id=1, sql=raw_sql)

    assert result.is_allowed is True
    assert result.status == "APPROVED"
    assert "employees" in result.applied_row_filters
    assert result.applied_row_filters["employees"] == "department_id = 4"
    assert result.injected_sql is not None
    assert "department_id = 4" in result.injected_sql

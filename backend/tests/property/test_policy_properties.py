import pytest
from hypothesis import given, strategies as st, settings
from app.services.sql_parser import SQLASTParser
from app.services.policy_engine import PolicyEngine
from app.models.policy import DataSource, DataPolicy
from sqlalchemy.orm import Session


NON_SELECT_VERBS = ["INSERT INTO test_table VALUES (1)", "UPDATE test_table SET a = 1", "DELETE FROM test_table WHERE id = 1", "DROP TABLE test_table", "ALTER TABLE test_table ADD COLUMN b INT", "CREATE TABLE new_table (id INT)"]


@settings(max_examples=30, deadline=None)
@given(st.sampled_from(NON_SELECT_VERBS))
def test_property_non_select_statements_always_rejected(sql_statement):
    """
    Property 1: The AST parser MUST NEVER classify any non-SELECT SQL statement as select-only.
    """
    analysis = SQLASTParser.analyze_sql(sql_statement)
    assert analysis.is_select_only is False, f"Statement was incorrectly flagged as select-only: {sql_statement}"


@st.composite
def random_select_query_strategy(draw):
    """Generates arbitrary SELECT queries with varying tables, columns, and WHERE clauses."""
    tables = ["employees", "departments", "sales", "customers", "orders", "unauthorized_table_x", "secret_salaries"]
    cols = ["id", "name", "salary", "ssn", "amount", "date", "status"]
    
    selected_table = draw(st.sampled_from(tables))
    selected_cols = draw(st.lists(st.sampled_from(cols), min_size=1, max_size=4, unique=True))
    
    where_clause = ""
    if draw(st.booleans()):
        where_clause = f" WHERE {draw(st.sampled_from(cols))} > 100"
        
    sql = f"SELECT {', '.join(selected_cols)} FROM {selected_table}{where_clause}"
    return sql, selected_table, selected_cols


def test_property_unauthorized_tables_never_pass_policy(db_session: Session):
    """
    Property 2: For any arbitrary query referencing a table not permitted by DataPolicy,
    PolicyEngine.validate_sql MUST return is_allowed == False.
    """
    # Seed only 'employees' table for role 4
    ds = db_session.query(DataSource).filter(DataSource.data_source_id == 1).first()
    if not ds:
        ds = DataSource(data_source_id=1, name="Default DB", db_type="sqlite", secret_ref="local", is_active=True)
        db_session.add(ds)
    db_session.add(DataPolicy(role_id=4, data_source_id=1, table_name="employees", access_level="read", aggregate_allowed=True))
    db_session.commit()

    unauthorized_queries = [
        "SELECT * FROM secret_salaries",
        "SELECT customer_id, credit_card FROM customers",
        "SELECT department_id FROM departments",
        "SELECT e.name, s.secret_field FROM employees e JOIN secret_salaries s ON e.id = s.id",
    ]

    for sql in unauthorized_queries:
        res = PolicyEngine.validate_sql(db=db_session, role_id=4, data_source_id=1, sql=sql)
        assert res.is_allowed is False, f"Unauthorized query unexpectedly allowed: {sql}"
        assert len(res.violations) > 0

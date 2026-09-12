import pytest
from app.services.sql_parser import SQLASTParser
from app.services.policy_engine import PolicyEngine
from app.models.policy import DataPolicy, SemanticCatalog, DataSource
from sqlalchemy.orm import Session


DANGEROUS_FUNCTION_QUERIES = [
    "SELECT pg_sleep(5) FROM employees;",
    "SELECT sleep(10) FROM customers;",
    "SELECT benchmark(10000000, MD5(1)) FROM sales;",
    "SELECT dblink('host=evil.com', 'SELECT 1') FROM orders;",
    "SELECT dblink_exec('host=evil.com', 'DROP TABLE users') FROM products;",
    "SELECT pg_read_file('/etc/passwd') FROM employees;",
    "SELECT pg_read_binary_file('/etc/shadow') FROM employees;",
    "SELECT pg_write_file('/tmp/hacked.txt', 'pwned', false) FROM employees;",
    "SELECT pg_ls_dir('/var/lib/postgresql') FROM departments;",
    "SELECT lo_export(12345, '/tmp/export.bin') FROM orders;",
    "SELECT lo_import('/tmp/backdoor.so') FROM orders;",
    "SELECT xp_cmdshell('whoami') FROM sales;",
    "SELECT sys_eval('id') FROM customers;",
    "SELECT sys_exec('rm -rf /') FROM products;",
    "SELECT version() FROM employees;",
    "SELECT current_user() FROM employees;",
    "SELECT session_user() FROM customers;",
    "SELECT inet_client_addr() FROM sales;",
    "SELECT inet_server_addr() FROM orders;",
    "SELECT pg_terminate_backend(12345) FROM employees;",
]

SAFE_FUNCTION_QUERIES = [
    "SELECT COUNT(*) AS total_emps FROM employees;",
    "SELECT AVG(price) AS avg_price FROM products;",
    "SELECT SUM(sale_amount) AS total_revenue FROM sales;",
    "SELECT MIN(order_date) AS first_order, MAX(order_date) AS last_order FROM orders;",
    "SELECT ROUND(AVG(price), 2) AS rounded_avg FROM products;",
    "SELECT COALESCE(description, 'No description') FROM products;",
    "SELECT UPPER(customer_name), LOWER(city) FROM customers;",
    "SELECT CONCAT(first_name, ' ', 'Employee') FROM employees;",
    "SELECT DATE_TRUNC('month', order_date) AS order_month, COUNT(*) FROM orders GROUP BY DATE_TRUNC('month', order_date);",
    "SELECT EXTRACT(YEAR FROM order_date) AS order_year FROM orders;",
]


def test_disallowed_functions_detected():
    """Task T-19 / Rule R1.3: Disallowed/side-channel functions must be detected in AST."""
    for sql in DANGEROUS_FUNCTION_QUERIES:
        res = SQLASTParser.analyze_sql(sql)
        assert len(res.disallowed_functions) > 0, f"Failed to detect disallowed function in query: {sql}"


def test_safe_functions_permitted():
    """Safe analytical functions should not be flagged as disallowed."""
    for sql in SAFE_FUNCTION_QUERIES:
        res = SQLASTParser.analyze_sql(sql)
        assert len(res.disallowed_functions) == 0, f"Mistakenly flagged safe function query: {sql} ({res.disallowed_functions})"
        assert res.is_select_only is True


def test_policy_engine_rejects_disallowed_functions(db_session: Session):
    """Verifies that PolicyEngine rejects queries containing disallowed functions with DISALLOWED_FUNCTION violation."""
    ds = DataSource(data_source_id=1, name="Test DB", db_type="postgresql", secret_ref="env:SECRET")
    db_session.add(ds)
    db_session.add(DataPolicy(role_id=1, data_source_id=1, table_name="employees", access_level="read"))
    db_session.add(SemanticCatalog(data_source_id=1, table_name="employees", column_name="employee_id", semantic_type="id"))
    db_session.commit()

    sql = "SELECT pg_sleep(5), employee_id FROM employees;"
    result = PolicyEngine.validate_sql(db=db_session, role_id=1, data_source_id=1, sql=sql)

    assert result.is_allowed is False
    assert result.status == "REJECTED"
    assert any(v.violation_type.value == "DISALLOWED_FUNCTION" and v.function_name == "PG_SLEEP" for v in result.violations)

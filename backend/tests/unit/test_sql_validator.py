import pytest
from app.services.sql_parser import SQLASTParser


# 20+ distinct non-SELECT statements, malicious attempts, and edge cases (Task T-15 / REQ-SAFE-01 / Rule R1.1)
NON_SELECT_STATEMENTS = [
    # 1. Direct DDL / DML
    "DROP TABLE employees;",
    "DROP TABLE IF EXISTS orders CASCADE;",
    "DELETE FROM customers WHERE id = 1;",
    "DELETE FROM sales;",
    "UPDATE employees SET salary = salary * 2;",
    "UPDATE customers SET email = 'hacked@evil.com';",
    "INSERT INTO employees (name, salary) VALUES ('Attacker', 100000);",
    "TRUNCATE TABLE sales;",
    "ALTER TABLE employees ADD COLUMN ssn VARCHAR(20);",
    "ALTER TABLE orders DROP COLUMN customer_id;",
    
    # 2. Permission / Grant attacks
    "GRANT ALL PRIVILEGES ON DATABASE mydb TO attacker;",
    "REVOKE SELECT ON employees FROM viewer;",
    
    # 3. Stacked queries / multi-statement injection
    "SELECT * FROM employees; DROP TABLE employees;",
    "SELECT 1; UPDATE customers SET balance = 0;",
    "SELECT count(*) FROM orders; DELETE FROM sales;",
    "SELECT name FROM employees; INSERT INTO audit_logs VALUES ('pwned');",
    
    # 4. File / Outfile writes
    "SELECT * INTO OUTFILE '/tmp/employees.csv' FROM employees;",
    
    # 5. Schema / Table creation
    "CREATE TABLE backdoor (id int, payload text);",
    "CREATE USER hacker WITH PASSWORD 'password';",
    
    # 6. Malicious CTE attempts (inserting / deleting inside CTE)
    "WITH deleted AS (DELETE FROM employees RETURNING *) SELECT * FROM deleted;",
    "WITH inserted AS (INSERT INTO employees (name) VALUES ('x') RETURNING *) SELECT * FROM inserted;",
    
    # 7. Execution / Procedure calls
    "EXEC sp_executesql N'DROP TABLE employees';",
    "CALL drop_all_tables();",
    
    # 8. Transaction / Session manipulation
    "COMMIT;",
    "ROLLBACK;",
    "SET search_path TO evil_schema;",
]

VALID_SELECT_STATEMENTS = [
    "SELECT employee_id, first_name, salary FROM employees WHERE department_id = 2;",
    "SELECT COUNT(*) AS total_orders, status FROM orders GROUP BY status;",
    "SELECT c.customer_name, SUM(s.sale_amount) FROM customers c JOIN sales s ON c.customer_id = s.customer_id GROUP BY c.customer_name;",
    "WITH active_users AS (SELECT user_id FROM sessions WHERE is_active = true) SELECT * FROM active_users;",
    "SELECT e.first_name, (SELECT MAX(sale_amount) FROM sales s WHERE s.employee_id = e.employee_id) AS top_sale FROM employees e;",
]


def test_reject_100_percent_non_select_statements():
    """Task T-15 / REQ-SAFE-01: Rejects 100% of non-SELECT statements in test set."""
    rejection_count = 0
    total_statements = len(NON_SELECT_STATEMENTS)

    for stmt in NON_SELECT_STATEMENTS:
        result = SQLASTParser.analyze_sql(stmt)
        if not result.is_select_only or not result.is_valid_syntax:
            rejection_count += 1
        else:
            pytest.fail(f"Non-SELECT statement was mistakenly accepted: {stmt}")

    assert rejection_count == total_statements, (
        f"Expected 100% rejection ({total_statements}/{total_statements}), but only got {rejection_count}"
    )


def test_accept_valid_select_statements():
    """Valid analytical SELECT statements must parse and pass statement-type validation."""
    for stmt in VALID_SELECT_STATEMENTS:
        result = SQLASTParser.analyze_sql(stmt)
        assert result.is_valid_syntax is True, f"Failed syntax on valid query: {result.syntax_error}"
        assert result.is_select_only is True, f"Valid SELECT marked non-select: {stmt}"


def test_table_and_column_extraction():
    """Verifies that physical tables and columns are accurately extracted from AST."""
    sql = "SELECT e.first_name, e.salary, d.department_name FROM employees e JOIN departments d ON e.department_id = d.department_id WHERE e.salary > 50000;"
    result = SQLASTParser.analyze_sql(sql)

    assert "employees" in result.tables
    assert "departments" in result.tables
    assert "salary" in result.table_columns.get("employees", [])
    assert "first_name" in result.table_columns.get("employees", [])
    assert "department_name" in result.table_columns.get("departments", [])


def test_aggregate_function_detection():
    """Verifies that aggregate functions like AVG, SUM, COUNT are extracted with target columns."""
    sql = "SELECT d.department_name, AVG(e.salary) AS avg_sal, COUNT(e.employee_id) AS emp_count FROM employees e JOIN departments d ON e.department_id = d.department_id GROUP BY d.department_name;"
    result = SQLASTParser.analyze_sql(sql)

    assert len(result.aggregates) >= 2
    avg_entry = next((a for a in result.aggregates if a["function"] == "AVG"), None)
    assert avg_entry is not None
    assert avg_entry["table"] == "employees"
    assert avg_entry["column"] == "salary"

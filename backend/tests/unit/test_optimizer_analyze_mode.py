import pytest
from sqlalchemy import create_engine, text
from app.services.optimizer import QueryOptimizerService


@pytest.fixture
def sqlite_test_db():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE products (
                product_id INTEGER PRIMARY KEY,
                product_name TEXT,
                unit_price REAL,
                discontinued INTEGER
            );
        """))
        for i in range(50):
            conn.execute(
                text("INSERT INTO products VALUES (:id, :name, :price, :disc)"),
                {"id": i + 1, "name": f"Product {i+1}", "price": (i + 1) * 10.0, "disc": i % 2},
            )
        conn.commit()
    return engine


def test_optimizer_analyze_rejects_non_admin(sqlite_test_db):
    """
    Test that EXPLAIN ANALYZE is blocked for non-admin roles (REQ-OPT-02 / Rule R6.5).
    """
    sql = "SELECT * FROM products WHERE unit_price > 100;"

    for non_admin_role in ["analyst", "viewer", "executive", "guest"]:
        with pytest.raises(PermissionError) as exc_info:
            QueryOptimizerService.run_explain_analyze(
                sqlite_test_db,
                sql,
                role=non_admin_role,
            )
        assert "restricted to administrator" in str(exc_info.value)


def test_optimizer_analyze_allows_admin(sqlite_test_db):
    """
    Test that EXPLAIN ANALYZE succeeds for admin role and returns execution stats within sandbox limits (REQ-OPT-02).
    """
    sql = "SELECT * FROM products WHERE unit_price > 100;"
    plan_raw, plan_summary, exec_stats = QueryOptimizerService.run_explain_analyze(
        sqlite_test_db,
        sql,
        role="admin",
        timeout_seconds=5.0,
    )

    assert plan_summary["mode"] == "explain_analyze"
    assert "execution_time_ms" in exec_stats
    assert exec_stats.get("sandbox_status") == "success" or exec_stats.get("status") == "success"


def test_optimizer_analyze_generates_higher_confidence_suggestions(sqlite_test_db):
    """
    Verify that ANALYZE mode produces high confidence suggestions with live execution backing (REQ-OPT-02).
    """
    sql = "SELECT * FROM products WHERE unit_price > 200;"
    plan_raw, plan_summary, exec_stats = QueryOptimizerService.run_explain_analyze(
        sqlite_test_db,
        sql,
        role="admin",
    )
    suggestions = QueryOptimizerService.generate_suggestions(
        sqlite_test_db,
        sql,
        plan_raw,
        plan_summary,
        is_analyze=True,
        exec_stats=exec_stats,
    )

    assert len(suggestions) > 0
    filter_sugg = next((s for s in suggestions if s.issue_type == "sequential_scan_on_filtered_table"), None)
    assert filter_sugg is not None
    assert filter_sugg.confidence == "high"
    assert filter_sugg.suggested_ddl == "CREATE INDEX idx_products_unit_price ON products(unit_price);"

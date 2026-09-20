import pytest
from collections import Counter
from hypothesis import given, strategies as st, settings, HealthCheck
from sqlalchemy import create_engine, text
from app.services.optimizer import CostBasedJoinOptimizer
from app.services.execution_sandbox import ExecutionSandboxService


@pytest.fixture(scope="module")
def property_db_engine():
    """Provides an in-memory SQLite database populated with 5 interconnected tables."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE t1 (id INT PRIMARY KEY, val INT);"))
        conn.execute(text("CREATE TABLE t2 (id INT PRIMARY KEY, t1_id INT, val INT);"))
        conn.execute(text("CREATE TABLE t3 (id INT PRIMARY KEY, t2_id INT, val INT);"))
        conn.execute(text("CREATE TABLE t4 (id INT PRIMARY KEY, t3_id INT, val INT);"))
        conn.execute(text("CREATE TABLE t5 (id INT PRIMARY KEY, t4_id INT, val INT);"))

        # Seed data
        conn.execute(text("INSERT INTO t1 VALUES (1, 10), (2, 20), (3, 30), (4, 40), (5, 50);"))
        conn.execute(text("INSERT INTO t2 VALUES (1, 1, 100), (2, 2, 200), (3, 3, 300), (4, 4, 400), (5, 5, 500);"))
        conn.execute(text("INSERT INTO t3 VALUES (1, 1, 1000), (2, 2, 2000), (3, 3, 3000), (4, 4, 4000), (5, 5, 5000);"))
        conn.execute(text("INSERT INTO t4 VALUES (1, 1, 10000), (2, 2, 20000), (3, 3, 30000), (4, 4, 40000), (5, 5, 50000);"))
        conn.execute(text("INSERT INTO t5 VALUES (1, 1, 100000), (2, 2, 200000), (3, 3, 300000), (4, 4, 400000), (5, 5, 500000);"))
        conn.commit()
    return engine


@given(
    join_depth=st.integers(min_value=2, max_value=5),
    filter_val=st.integers(min_value=0, max_value=40),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_hypothesis_join_graph_semantic_equivalence(property_db_engine, join_depth, filter_val):
    """
    Property-Based Test (Hypothesis):
    Validates semantic preservation across randomly generated join graph depths (2 to 5 tables)
    with selective filters.
    """
    from_clause = "t1"
    joins = []
    select_cols = ["t1.val AS v1"]

    for i in range(2, join_depth + 1):
        prev_tbl = f"t{i-1}"
        curr_tbl = f"t{i}"
        joins.append(f"JOIN {curr_tbl} ON {prev_tbl}.id = {curr_tbl}.{prev_tbl}_id")
        select_cols.append(f"{curr_tbl}.val AS v{i}")

    where_clause = f"WHERE t1.val >= {filter_val}"
    sql = f"SELECT {', '.join(select_cols)} FROM {from_clause} {' '.join(joins)} {where_clause};"

    plan = CostBasedJoinOptimizer.optimize_query(sql, engine=property_db_engine)
    opt_sql = plan.optimized_sql or sql

    res_orig = ExecutionSandboxService.execute_query(property_db_engine, sql)
    res_opt = ExecutionSandboxService.execute_query(property_db_engine, opt_sql)

    assert res_orig.success is True, f"Original SQL failed: {res_orig.error}"
    assert res_opt.success is True, f"Optimized SQL failed: {res_opt.error}"
    assert res_orig.row_count == res_opt.row_count

    orig_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in res_orig.rows]
    opt_tuples = [tuple(sorted((k, v) for k, v in r.items())) for r in res_opt.rows]
    assert Counter(orig_tuples) == Counter(opt_tuples)


@pytest.mark.parametrize(
    "query,expected_bypass_reason",
    [
        (
            "SELECT a.id, b.val FROM t1 a JOIN t2 b ON a.id > b.t1_id",
            "NON_EQUI_OR_COMPLEX_JOIN_PREDICATE",
        ),
        (
            "SELECT a.id, b.val FROM t1 a LEFT JOIN t2 b ON a.id = b.t1_id",
            "OUTER_JOIN_UNSUPPORTED_LEFT",
        ),
        (
            "WITH cte AS (SELECT id, val FROM t1) SELECT c.id, b.val FROM cte c JOIN t2 b ON c.id = b.t1_id",
            "CTE_EXPRESSION_PRESENT",
        ),
        (
            "SELECT a.id, b.val FROM t1 a JOIN t2 b ON a.id = b.t1_id WHERE a.id IN (SELECT t1_id FROM t2)",
            "NESTED_SUBQUERY_PRESENT",
        ),
        (
            "SELECT a.id, ROW_NUMBER() OVER (PARTITION BY a.val ORDER BY a.id) as rn FROM t1 a JOIN t2 b ON a.id = b.t1_id",
            "WINDOW_FUNCTION_PRESENT",
        ),
        (
            "SELECT a.id, RANDOM() FROM t1 a JOIN t2 b ON a.id = b.t1_id",
            "VOLATILE_FUNCTION_RANDOM",
        ),
        (
            "SELECT id, val FROM t1 UNION SELECT id, val FROM t2",
            "SET_OPERATION_PRESENT",
        ),
    ],
)
def test_optimizer_unsafe_query_shape_matrix(query, expected_bypass_reason):
    """
    Unsafe Query Shape Matrix:
    Asserts that all non-supported query shapes (non-equi, outer joins, CTEs, subqueries,
    window functions, volatile functions, set operations) are safely bypassed by the optimizer,
    leaving the original SQL intact.
    """
    plan = CostBasedJoinOptimizer.optimize_query(query)
    assert plan.search_strategy.startswith("BYPASS")
    assert plan.optimized_sql == query
    assert expected_bypass_reason in plan.search_strategy or expected_bypass_reason in plan.gate_reason

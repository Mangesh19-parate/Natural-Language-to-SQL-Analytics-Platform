import pytest
from sqlalchemy import create_engine, text
from app.schemas.agent import PlanSubTask
from app.services.dag_validator import DAGValidator, DAGValidationError
from app.services.join_optimizer import (
    CostBasedJoinOptimizer,
    JoinGraph,
    JoinEdge,
    DEFAULT_TABLE_STATS,
    TableStatsProvider,
    CalibratedTableStats,
)
from app.schemas.optimize import (
    JoinAlgorithmEnum,
    GateDecisionEnum,
)


def test_kahn_topological_sort_correctness():
    """Verify that Kahn's algorithm produces valid topological execution order in O(V+E)."""
    tasks = [
        PlanSubTask(step_id=1, task_name="Fetch Customer Orders", description="Fetch", sql_intent="Fetch", dependencies=[]),
        PlanSubTask(step_id=2, task_name="Aggregate Sales Revenue", description="Aggregate", sql_intent="Aggregate", dependencies=[1]),
        PlanSubTask(step_id=3, task_name="Compute Department Attribution", description="Attribution", sql_intent="Attribution", dependencies=[1]),
        PlanSubTask(step_id=4, task_name="Synthesize Final Report", description="Synthesize", sql_intent="Synthesize", dependencies=[2, 3]),
    ]

    ordered = DAGValidator.validate_and_order_dag(tasks)
    step_indices = {task.step_id: idx for idx, task in enumerate(ordered)}

    assert step_indices[1] < step_indices[2]
    assert step_indices[1] < step_indices[3]
    assert step_indices[2] < step_indices[4]
    assert step_indices[3] < step_indices[4]


def test_kahn_topological_sort_cycle_rejection():
    """Verify that cyclic dependencies are rejected by the Kahn topological validator."""
    cyclic_tasks = [
        PlanSubTask(step_id=1, task_name="Task A", description="A", sql_intent="A", dependencies=[2]),
        PlanSubTask(step_id=2, task_name="Task B", description="B", sql_intent="B", dependencies=[1]),
    ]
    with pytest.raises(DAGValidationError) as exc:
        DAGValidator.validate_and_order_dag(cyclic_tasks)
    assert "Cyclic dependency detected" in str(exc.value)


def test_join_graph_ast_extraction():
    """Verify that JoinGraph accurately extracts relation aliases and join edges from SQL AST."""
    sql = """
        SELECT c.customer_name, o.total_amount, s.revenue
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        JOIN sales s ON o.order_id = s.order_id
        WHERE c.city = 'London';
    """
    graph = JoinGraph(sql)
    assert set(graph.tables) == {"c", "o", "s"}
    assert graph.alias_to_table["c"] == "customers"
    assert graph.alias_to_table["o"] == "orders"
    assert graph.alias_to_table["s"] == "sales"
    assert len(graph.edges) >= 2

    # Filter on London should reduce selectivity for c
    assert graph.filter_selectivity["c"] < 1.0


def test_single_table_scan_plan():
    """Verify that single-table queries are handled with single-table scan strategy."""
    sql = "SELECT customer_name, total_spent FROM customers WHERE total_spent > 500;"
    resp = CostBasedJoinOptimizer.optimize_query(sql)

    assert resp.search_strategy == "SINGLE_TABLE"
    assert resp.subsets_evaluated == 1
    assert resp.gate_decision == GateDecisionEnum.ALLOW
    assert resp.plan_tree["operator"] in [JoinAlgorithmEnum.TABLE_SCAN.value, JoinAlgorithmEnum.INDEX_SCAN.value]


def test_two_table_join_optimization():
    """Verify 2-table join produces valid Hash/Nested Loop plan with cost estimation."""
    sql = """
        SELECT c.customer_name, o.total_amount
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id;
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)

    assert resp.search_strategy == "BITMASK_DYNAMIC_PROGRAMMING"
    assert resp.join_edges_count >= 1
    assert resp.gate_decision == GateDecisionEnum.ALLOW
    assert resp.optimal_cost > 0
    assert resp.plan_tree["operator"] in [JoinAlgorithmEnum.HASH_JOIN.value, JoinAlgorithmEnum.NESTED_LOOP_JOIN.value, JoinAlgorithmEnum.SORT_MERGE_JOIN.value]


def test_three_table_join_bitmask_dp():
    """Verify 3-table join searches 2^3=8 states and finds globally optimal join tree."""
    sql = """
        SELECT c.customer_name, p.product_name, s.revenue
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        JOIN sales s ON o.order_id = s.order_id
        JOIN products p ON s.product_id = p.product_id;
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)

    assert resp.search_strategy == "BITMASK_DYNAMIC_PROGRAMMING"
    assert resp.subsets_evaluated >= 4
    assert len(resp.tables) == 4
    assert resp.gate_decision == GateDecisionEnum.ALLOW
    assert resp.optimal_cost <= resp.naive_cost


def test_ast_join_rewriter_genuine_transformation():
    """Verify that optimizer generates genuinely rewritten SQL AST rather than comment-only decoration."""
    sql = """
        SELECT c.customer_name, o.total_amount, s.revenue
        FROM sales s
        JOIN orders o ON s.order_id = o.order_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.city = 'London';
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)
    opt_sql = resp.optimized_sql

    assert opt_sql is not None
    assert len(opt_sql) > 10
    # Must NOT be just a comment wrapper
    assert not opt_sql.startswith("-- Cost-Based Optimizer Rewritten Plan")
    # Must contain proper FROM and JOIN keywords
    assert "FROM" in opt_sql.upper()
    assert "JOIN" in opt_sql.upper()
    assert "WHERE" in opt_sql.upper()


def test_cartesian_product_block_gate():
    """Verify that cross joins without join predicates are blocked by the safety gate."""
    sql = """
        SELECT c.customer_name, p.product_name
        FROM customers c, products p;
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)

    assert resp.gate_decision == GateDecisionEnum.BLOCK_RUNAWAY_CARTESIAN
    assert "Cross join" in resp.gate_reason or "Cartesian" in resp.gate_reason


def test_cost_exceeded_strict_and_warn_gate():
    """Verify that queries exceeding cost threshold trigger BLOCK_EXPENSIVE (strict) or WARN_EXPENSIVE."""
    sql = """
        SELECT c.customer_name, o.total_amount
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id;
    """
    # Strict admission (default)
    resp_strict = CostBasedJoinOptimizer.optimize_query(sql, max_allowed_cost=0.01, strict_admission=True)
    assert resp_strict.gate_decision == GateDecisionEnum.BLOCK_EXPENSIVE
    assert "exceeds admission limit" in resp_strict.gate_reason

    # Permissive admission
    resp_warn = CostBasedJoinOptimizer.optimize_query(sql, max_allowed_cost=0.01, strict_admission=False)
    assert resp_warn.gate_decision == GateDecisionEnum.WARN_EXPENSIVE


def test_greedy_join_fallback_large_query():
    """Verify that join queries with >8 tables fallback to greedy priority queue solver."""
    sql = """
        SELECT *
        FROM t1
        JOIN t2 ON t1.id = t2.t1_id
        JOIN t3 ON t2.id = t3.t2_id
        JOIN t4 ON t3.id = t4.t3_id
        JOIN t5 ON t4.id = t5.t4_id
        JOIN t6 ON t5.id = t6.t5_id
        JOIN t7 ON t6.id = t7.t6_id
        JOIN t8 ON t7.id = t8.t7_id
        JOIN t9 ON t8.id = t9.t8_id;
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)

    assert resp.search_strategy == "GREEDY_MIN_SELECTIVITY"
    assert len(resp.tables) == 9
    assert resp.optimal_cost > 0
    assert resp.optimized_sql is not None


def test_table_stats_provider_live_engine():
    """Verify TableStatsProvider extracts real table row counts and primary keys from a live Engine."""
    test_engine = create_engine("sqlite:///:memory:")
    with test_engine.connect() as conn:
        conn.execute(text("CREATE TABLE test_users (id INTEGER PRIMARY KEY, name TEXT);"))
        conn.execute(text("INSERT INTO test_users (name) VALUES ('Alice'), ('Bob'), ('Charlie');"))
        conn.commit()

    stats_map, source = TableStatsProvider.get_stats_map(test_engine, force_refresh=True)
    assert source == "live_engine"
    assert "test_users" in stats_map
    assert stats_map["test_users"].tuple_count == 3.0
    assert stats_map["test_users"].primary_key == "id"


def test_execution_benchmarking_live_engine():
    """Verify benchmark_execution executes queries and asserts result set equivalence."""
    test_engine = create_engine("sqlite:///:memory:")
    with test_engine.connect() as conn:
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT);"))
        conn.execute(text("CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL);"))
        conn.execute(text("INSERT INTO customers VALUES (1, 'Alice'), (2, 'Bob');"))
        conn.execute(text("INSERT INTO orders VALUES (101, 1, 50.0), (102, 2, 75.0);"))
        conn.commit()

    orig_sql = "SELECT c.name, o.amount FROM customers c JOIN orders o ON c.id = o.customer_id;"
    opt_sql = "SELECT c.name, o.amount FROM orders o JOIN customers c ON c.id = o.customer_id;"

    bench = CostBasedJoinOptimizer.benchmark_execution(orig_sql, opt_sql, test_engine)
    assert bench.results_equivalent is True
    assert bench.row_count == 2
    assert bench.validation_status == "VERIFIED_EQUIVALENT"
    assert bench.original_exec_ms >= 0.0
    assert bench.optimized_exec_ms >= 0.0


def test_optimizer_shape_bypass_cte():
    """Verify that CTE queries are safely bypassed without destructive table flattening."""
    sql = """
        WITH dept_avg AS (
            SELECT department_id, AVG(salary) AS avg_sal
            FROM employees
            GROUP BY department_id
        )
        SELECT e.first_name, d.avg_sal
        FROM employees e
        JOIN dept_avg d ON e.department_id = d.department_id;
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)
    assert "BYPASS" in resp.search_strategy
    assert resp.gate_decision == GateDecisionEnum.ALLOW
    assert resp.optimized_sql == sql


def test_optimizer_shape_bypass_subquery():
    """Verify that nested subqueries in FROM/WHERE are safely bypassed."""
    sql = """
        SELECT c.customer_name
        FROM customers c
        WHERE c.customer_id IN (
            SELECT customer_id FROM orders WHERE total_amount > 500
        );
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)
    assert "BYPASS" in resp.search_strategy
    assert resp.optimized_sql == sql


def test_optimizer_outer_join_preservation():
    """Verify that LEFT/RIGHT/FULL outer joins are preserved without arbitrary reordering."""
    sql = """
        SELECT d.department_name, e.first_name
        FROM departments d
        LEFT JOIN employees e ON d.department_id = e.department_id;
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)
    assert resp.search_strategy == "PRESERVED_OUTER_JOIN"
    assert resp.gate_decision == GateDecisionEnum.ALLOW
    assert "LEFT JOIN" in resp.optimized_sql.upper()


def test_stats_provider_cache_isolation_per_data_source():
    """Verify that TableStatsProvider isolates cached statistics across distinct data sources."""
    engine1 = create_engine("sqlite:///:memory:")
    with engine1.connect() as conn:
        conn.execute(text("CREATE TABLE customers (id INT, name TEXT);"))
        conn.execute(text("INSERT INTO customers VALUES (1, 'Alice');"))
        conn.commit()

    engine2 = create_engine("sqlite:///:memory:")
    with engine2.connect() as conn:
        conn.execute(text("CREATE TABLE customers (id INT, name TEXT);"))
        conn.execute(text("INSERT INTO customers VALUES (1, 'Bob'), (2, 'Charlie'), (3, 'David');"))
        conn.commit()

    stats1, _ = TableStatsProvider.get_stats_map(engine1, data_source_id=1, force_refresh=True)
    stats2, _ = TableStatsProvider.get_stats_map(engine2, data_source_id=2, force_refresh=True)

    assert stats1["customers"].tuple_count == 1.0
    assert stats2["customers"].tuple_count == 3.0


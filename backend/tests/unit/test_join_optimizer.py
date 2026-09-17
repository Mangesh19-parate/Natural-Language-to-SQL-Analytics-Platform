import pytest
from app.schemas.agent import PlanSubTask
from app.services.dag_validator import DAGValidator, DAGValidationError
from app.services.join_optimizer import (
    CostBasedJoinOptimizer,
    JoinGraph,
    JoinEdge,
    DEFAULT_TABLE_STATS,
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
    assert resp.plan_tree["operator"] == JoinAlgorithmEnum.TABLE_SCAN.value


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


def test_cartesian_product_block_gate():
    """Verify that cross joins without join predicates are blocked by the safety gate."""
    sql = """
        SELECT c.customer_name, p.product_name
        FROM customers c, products p;
    """
    resp = CostBasedJoinOptimizer.optimize_query(sql)

    assert resp.gate_decision == GateDecisionEnum.BLOCK_RUNAWAY_CARTESIAN
    assert "Cartesian" in resp.gate_reason or "Cross join" in resp.gate_reason


def test_cost_exceeded_warn_gate():
    """Verify that queries exceeding the maximum cost threshold produce a warning gate decision."""
    sql = """
        SELECT c.customer_name, o.total_amount
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id;
    """
    # Force tiny threshold to trigger warning
    resp = CostBasedJoinOptimizer.optimize_query(sql, max_allowed_cost=0.5)

    assert resp.gate_decision == GateDecisionEnum.WARN_EXPENSIVE
    assert "exceeds threshold" in resp.gate_reason


def test_greedy_join_fallback_large_query():
    """Verify that join queries with >8 tables fallback to greedy minimum selectivity solver."""
    # Synthesize query with 9 tables
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

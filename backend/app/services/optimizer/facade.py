import math
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import Engine

from app.schemas.optimize import (
    JoinAlgorithmEnum,
    GateDecisionEnum,
    JoinPlanResponse,
    ExecutionBenchmarkResult,
)
from app.services.optimizer.models import CalibratedTableStats, PhysicalPlanNode
from app.services.optimizer.stats_provider import TableStatsProvider
from app.services.optimizer.join_graph import JoinGraph
from app.services.optimizer.cost_model import PAGE_IO_COST, CPU_TUPLE_COST, CPU_INDEX_TUPLE_COST
from app.services.optimizer.bitmask_dp import solve_bitmask_dp
from app.services.optimizer.greedy_heap import solve_greedy, compute_naive_left_deep
from app.services.optimizer.rewriter import generate_optimized_sql
from app.services.optimizer.benchmark import benchmark_execution


class CostBasedJoinOptimizer:
    """
    Selinger-Inspired Cost-Based Join-Planning Subsystem (Educational Cost Model).
    Provides application-level estimated physical plans and deterministic admission gating.
    Algorithms:
    - Bitmask Dynamic Programming (O(3^N) optimal solver for N <= 8)
    - Min-Heap Priority Queue Greedy Solver (O(N^2 log N) for N > 8)
    - AST Query Rewriter strictly restricted to commutative/associative INNER equi-joins
    - Formal Shape Guards (Automatic safe bypass for CTEs, subqueries, volatile functions, and outer joins)
    - Multi-Trial Empirical Benchmarking
    - Deterministic Admission Gate against Cartesian row explosion and runaway resource costs
    """

    @classmethod
    def optimize_query(
        cls,
        sql: str,
        custom_stats: Optional[Dict[str, CalibratedTableStats]] = None,
        engine: Optional[Engine] = None,
        data_source_id: int = 1,
        max_allowed_cost: float = 50000.0,
        strict_admission: bool = True,
        benchmark: bool = False,
    ) -> JoinPlanResponse:
        """
        Computes an estimated physical join plan for a SQL query,
        rewrites the AST with optimal join ordering where semantics are guaranteed to be preserved,
        and evaluates deterministic admission safety.
        """
        # 1. Resolve table statistics map with multi-tenant isolation
        if custom_stats:
            stats_map = custom_stats
            stats_source = "custom"
        else:
            stats_map, stats_source = TableStatsProvider.get_stats_map(engine=engine, data_source_id=data_source_id)

        graph = JoinGraph(sql, stats_map)
        num_tables = len(graph.tables)
        indexes_used: List[str] = []

        # 2. Guard against unsupported query shapes
        if not graph.is_shape_supported:
            return JoinPlanResponse(
                original_sql=sql,
                optimized_sql=sql,
                tables=graph.tables,
                join_edges_count=len(graph.edges),
                search_strategy=f"BYPASS_{graph.unsupported_reason or 'COMPLEX_SHAPE'}",
                subsets_evaluated=0,
                naive_cost=10.0,
                optimal_cost=10.0,
                cost_reduction_pct=0.0,
                gate_decision=GateDecisionEnum.ALLOW,
                gate_reason=f"Query shape bypassed by optimizer: {graph.unsupported_reason}",
                plan_tree={"operator": "UNMODIFIED_QUERY_PASS_THROUGH", "cost": 10.0, "cardinality": 10.0},
                indexes_used=[],
                stats_source=stats_source,
                execution_benchmark=None,
                execution_recommendation=f"Bypassed: {graph.unsupported_reason}. Unmodified original query passed through safely.",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        if num_tables == 0:
            return JoinPlanResponse(
                original_sql=sql,
                optimized_sql=sql,
                tables=[],
                join_edges_count=0,
                search_strategy="NON_RELATIONAL",
                subsets_evaluated=0,
                naive_cost=0.1,
                optimal_cost=0.1,
                cost_reduction_pct=0.0,
                gate_decision=GateDecisionEnum.ALLOW,
                gate_reason="Non-relational query",
                plan_tree={"operator": "CONSTANT_SCAN", "cost": 0.1, "cardinality": 1.0},
                indexes_used=[],
                stats_source=stats_source,
                execution_benchmark=None,
                execution_recommendation="Safe for immediate execution",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        if num_tables == 1:
            alias = graph.tables[0]
            card = graph.get_table_cardinality(alias)
            pages = graph.get_table_pages(alias)
            is_idx, idx_name = graph.is_table_indexed_for_query(alias)
            if is_idx and idx_name:
                indexes_used.append(f"{alias}.{idx_name}")
                op = JoinAlgorithmEnum.INDEX_SCAN
                pages_est = max(1.0, math.ceil(math.log2(max(pages, 2.0))))
                cost = pages_est * PAGE_IO_COST + card * CPU_INDEX_TUPLE_COST
            else:
                op = JoinAlgorithmEnum.TABLE_SCAN
                cost = pages * PAGE_IO_COST + card * CPU_TUPLE_COST

            plan = PhysicalPlanNode(
                operator=op,
                cardinality=card,
                cost=cost,
                tables_mask=1,
                table_name=graph.alias_to_table.get(alias, alias),
                alias=alias,
            )
            rec_note = "Single-table query verified with estimated scan plan."
            if graph.has_insufficient_stats or stats_source != "live_engine":
                rec_note += " (Confidence: LOW - Educational Selinger Heuristic)"

            return JoinPlanResponse(
                original_sql=sql,
                optimized_sql=sql,
                tables=graph.tables,
                join_edges_count=0,
                search_strategy="SINGLE_TABLE",
                subsets_evaluated=1,
                naive_cost=round(cost, 2),
                optimal_cost=round(cost, 2),
                cost_reduction_pct=0.0,
                gate_decision=GateDecisionEnum.ALLOW,
                gate_reason="Single table scan within cost limit",
                plan_tree=plan.to_dict(),
                indexes_used=indexes_used,
                stats_source=stats_source,
                execution_benchmark=None,
                execution_recommendation=rec_note,
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        # Multi-table join optimization
        if num_tables <= 8:
            optimal_plan, subsets_eval = solve_bitmask_dp(graph)
            strategy = "BITMASK_DYNAMIC_PROGRAMMING"
        else:
            optimal_plan, subsets_eval = solve_greedy(graph)
            strategy = "GREEDY_MIN_SELECTIVITY"

        cls._collect_indexes_used(optimal_plan, graph, indexes_used)

        naive_plan = compute_naive_left_deep(graph)
        naive_cost = max(naive_plan.cost, 1.0)
        optimal_cost = optimal_plan.cost
        reduction_pct = max(0.0, round(((naive_cost - optimal_cost) / naive_cost) * 100.0, 1))

        # Cartesian explosion check
        has_cross_join = len(graph.edges) == 0 and num_tables > 1
        
        if has_cross_join:
            gate_decision = GateDecisionEnum.BLOCK_RUNAWAY_CARTESIAN
            gate_reason = f"Cross join detected across {num_tables} tables with 0 join predicates. Rejected by optimizer admission gate."
            rec = "CRITICAL: Missing JOIN ON predicates will cause Cartesian row explosion. Execution blocked."
        elif optimal_cost > max_allowed_cost:
            gate_decision = GateDecisionEnum.BLOCK_EXPENSIVE if strict_admission else GateDecisionEnum.WARN_EXPENSIVE
            gate_reason = f"Estimated cost ({round(optimal_cost, 1)}) exceeds admission limit ({max_allowed_cost})."
            rec = "High-cost execution blocked by admission gate. Add indexed filters or restrict join scope."
        else:
            gate_decision = GateDecisionEnum.ALLOW
            gate_reason = f"Cost ({round(optimal_cost, 1)}) is within deterministic resource threshold."
            rec = f"Optimal join order computed using {strategy} (Selinger-inspired model). Estimated cost reduction: {reduction_pct}%."

        if graph.has_insufficient_stats or stats_source != "live_engine":
            rec += " [Confidence: LOW - Statistics uncalibrated / heuristic fallback]"

        # Safe AST rewrite: Only rewrite purely associative/commutative INNER joins
        if graph.has_outer_join:
            optimized_sql = sql
            rec += " (Outer joins preserved without reordering to guarantee semantic invariance)."
        else:
            optimized_sql = generate_optimized_sql(graph, optimal_plan, sql)

        # Multi-trial execution benchmark profiling
        exec_benchmark = None
        if benchmark and engine and gate_decision == GateDecisionEnum.ALLOW:
            exec_benchmark = benchmark_execution(sql, optimized_sql, engine)

        return JoinPlanResponse(
            original_sql=sql,
            optimized_sql=optimized_sql,
            tables=graph.tables,
            join_edges_count=len(graph.edges),
            search_strategy=strategy if not graph.has_outer_join else "PRESERVED_OUTER_JOIN",
            subsets_evaluated=subsets_eval,
            naive_cost=round(naive_cost, 2),
            optimal_cost=round(optimal_cost, 2),
            cost_reduction_pct=reduction_pct,
            gate_decision=gate_decision,
            gate_reason=gate_reason,
            plan_tree=optimal_plan.to_dict(),
            indexes_used=indexes_used,
            stats_source=stats_source,
            execution_benchmark=exec_benchmark,
            execution_recommendation=rec,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def _collect_indexes_used(cls, node: PhysicalPlanNode, graph: JoinGraph, out_list: List[str]):
        if node.operator == JoinAlgorithmEnum.INDEX_SCAN and node.alias:
            is_idx, idx_name = graph.is_table_indexed_for_query(node.alias)
            if idx_name:
                out_list.append(f"{node.alias}.{idx_name}")
        if node.left_child:
            cls._collect_indexes_used(node.left_child, graph, out_list)
        if node.right_child:
            cls._collect_indexes_used(node.right_child, graph, out_list)

    @classmethod
    def benchmark_execution(
        cls,
        original_sql: str,
        optimized_sql: str,
        engine: Engine,
        max_rows: int = 1000,
        warmup_trials: int = 2,
        timed_trials: int = 5,
    ) -> ExecutionBenchmarkResult:
        """Multi-trial execution profiling delegator."""
        return benchmark_execution(
            original_sql=original_sql,
            optimized_sql=optimized_sql,
            engine=engine,
            max_rows=max_rows,
            warmup_trials=warmup_trials,
            timed_trials=timed_trials,
        )

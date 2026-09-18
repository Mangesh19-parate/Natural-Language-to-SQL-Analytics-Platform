"""
Backward compatibility shim for app.services.join_optimizer.
The optimizer has been modularized into app.services.optimizer package.
"""

from app.schemas.optimize import (
    JoinAlgorithmEnum,
    GateDecisionEnum,
    JoinPlanResponse,
    JoinPlanRequest,
    ExecutionBenchmarkResult,
)
from app.services.optimizer import (
    CalibratedTableStats,
    CostBasedJoinOptimizer,
    DEFAULT_TABLE_STATS,
    JoinEdge,
    PhysicalPlanNode,
    TableStatsProvider,
    JoinGraph,
    solve_bitmask_dp,
    solve_greedy,
    compute_naive_left_deep,
    generate_optimized_sql,
    extract_ordered_aliases,
    benchmark_execution,
    PAGE_IO_COST,
    CPU_TUPLE_COST,
    CPU_INDEX_TUPLE_COST,
    CPU_HASH_COST,
    CPU_SORT_COST,
    calculate_join_cost,
    QueryOptimizerService,
)

__all__ = [
    "JoinAlgorithmEnum",
    "GateDecisionEnum",
    "JoinPlanResponse",
    "JoinPlanRequest",
    "ExecutionBenchmarkResult",
    "CalibratedTableStats",
    "CostBasedJoinOptimizer",
    "DEFAULT_TABLE_STATS",
    "JoinEdge",
    "PhysicalPlanNode",
    "TableStatsProvider",
    "JoinGraph",
    "solve_bitmask_dp",
    "solve_greedy",
    "compute_naive_left_deep",
    "generate_optimized_sql",
    "extract_ordered_aliases",
    "benchmark_execution",
    "PAGE_IO_COST",
    "CPU_TUPLE_COST",
    "CPU_INDEX_TUPLE_COST",
    "CPU_HASH_COST",
    "CPU_SORT_COST",
    "calculate_join_cost",
    "QueryOptimizerService",
]

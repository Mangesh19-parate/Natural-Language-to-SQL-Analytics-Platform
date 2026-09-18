import math
from typing import List, Tuple
from app.schemas.optimize import JoinAlgorithmEnum
from app.services.optimizer.models import PhysicalPlanNode, JoinEdge

# Selinger-inspired deterministic educational cost constants
PAGE_IO_COST = 1.0            # Cost of 1 8KB disk page I/O fetch
CPU_TUPLE_COST = 0.01         # Cost of processing 1 row in CPU
CPU_INDEX_TUPLE_COST = 0.005  # Cost of index binary search per tuple
CPU_HASH_COST = 0.02          # Cost of hashing key + hash table insert/probe
CPU_SORT_COST = 0.03          # Cost of N log N sort comparison per tuple


def calculate_join_cost(
    plan1: PhysicalPlanNode,
    plan2: PhysicalPlanNode,
    connecting_edges: List[JoinEdge],
    selectivity: float,
) -> Tuple[JoinAlgorithmEnum, float, float]:
    """
    Computes the estimated physical join algorithm and associated cost consistently across planners.
    Returns: (best_operator, estimated_cardinality, total_cost)
    """
    out_card = max(1.0, plan1.cardinality * plan2.cardinality * selectivity)

    # 1. Hash Join
    hj_cost = plan1.cost + plan2.cost + (plan1.cardinality + plan2.cardinality) * CPU_HASH_COST
    
    # 2. Nested Loop Join
    nlj_cost = plan1.cost + plan1.cardinality * plan2.cost + (plan1.cardinality * plan2.cardinality) * CPU_TUPLE_COST
    
    # 3. Sort Merge Join
    smj_cost = (
        plan1.cost
        + plan2.cost
        + (
            plan1.cardinality * math.log2(max(plan1.cardinality, 2.0))
            + plan2.cardinality * math.log2(max(plan2.cardinality, 2.0))
        )
        * CPU_SORT_COST
        + (plan1.cardinality + plan2.cardinality) * CPU_TUPLE_COST
    )

    if not connecting_edges:
        hj_cost *= 10.0
        nlj_cost *= 10.0
        smj_cost *= 10.0

    best_op = JoinAlgorithmEnum.HASH_JOIN
    min_cost = hj_cost
    if nlj_cost < min_cost and connecting_edges:
        min_cost = nlj_cost
        best_op = JoinAlgorithmEnum.NESTED_LOOP_JOIN
    if smj_cost < min_cost and connecting_edges:
        min_cost = smj_cost
        best_op = JoinAlgorithmEnum.SORT_MERGE_JOIN

    return best_op, out_card, min_cost

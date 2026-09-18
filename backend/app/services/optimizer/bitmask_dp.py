import math
from typing import Dict, Tuple, Optional
from app.schemas.optimize import JoinAlgorithmEnum
from app.services.optimizer.models import PhysicalPlanNode
from app.services.optimizer.join_graph import JoinGraph
from app.services.optimizer.cost_model import PAGE_IO_COST, CPU_TUPLE_COST, CPU_INDEX_TUPLE_COST, calculate_join_cost


def solve_bitmask_dp(graph: JoinGraph) -> Tuple[PhysicalPlanNode, int]:
    """
    Solves optimal join ordering using Dynamic Programming over Bitmask states in O(3^N).
    """
    N = len(graph.tables)
    dp: Dict[int, PhysicalPlanNode] = {}
    subsets_evaluated = 0

    # 1. Base cases: Single table scans for each singleton bitmask
    for i in range(N):
        alias = graph.tables[i]
        mask = 1 << i
        card = graph.get_table_cardinality(alias)
        pages = graph.get_table_pages(alias)
        is_idx, idx_name = graph.is_table_indexed_for_query(alias)
        if is_idx:
            op = JoinAlgorithmEnum.INDEX_SCAN
            pages_est = max(1.0, math.ceil(math.log2(max(pages, 2.0))))
            cost = pages_est * PAGE_IO_COST + card * CPU_INDEX_TUPLE_COST
        else:
            op = JoinAlgorithmEnum.TABLE_SCAN
            cost = pages * PAGE_IO_COST + card * CPU_TUPLE_COST

        dp[mask] = PhysicalPlanNode(
            operator=op,
            cardinality=card,
            cost=cost,
            tables_mask=mask,
            table_name=graph.alias_to_table.get(alias, alias),
            alias=alias,
        )
        subsets_evaluated += 1

    # 2. Iterate subset sizes from 2 to N
    for s in range(2, N + 1):
        for mask in range(1, 1 << N):
            if bin(mask).count("1") != s:
                continue

            best_node_for_mask: Optional[PhysicalPlanNode] = None

            s1 = (mask - 1) & mask
            while s1 > 0:
                s2 = mask ^ s1
                if s1 < s2:  # Symmetric evaluation reduction
                    plan1 = dp.get(s1)
                    plan2 = dp.get(s2)

                    if plan1 and plan2:
                        subsets_evaluated += 1
                        aliases1 = [graph.tables[i] for i in range(N) if (s1 & (1 << i))]
                        aliases2 = [graph.tables[i] for i in range(N) if (s2 & (1 << i))]

                        connecting_edges = graph.find_connecting_edges(aliases1, aliases2)
                        sel = graph.compute_join_selectivity(connecting_edges, plan1.cardinality, plan2.cardinality)
                        best_op, out_card, min_join_cost = calculate_join_cost(plan1, plan2, connecting_edges, sel)
                        pred_str = " AND ".join(e.raw_predicate for e in connecting_edges) if connecting_edges else "CROSS JOIN"

                        candidate = PhysicalPlanNode(
                            operator=best_op,
                            cardinality=out_card,
                            cost=min_join_cost,
                            tables_mask=mask,
                            join_predicate=pred_str,
                            left_child=plan1,
                            right_child=plan2,
                        )

                        if best_node_for_mask is None or candidate.cost < best_node_for_mask.cost:
                            best_node_for_mask = candidate

                s1 = (s1 - 1) & mask

            if best_node_for_mask:
                dp[mask] = best_node_for_mask

    root_mask = (1 << N) - 1
    return dp[root_mask], subsets_evaluated

import math
import heapq
from typing import Dict, List, Tuple
from app.schemas.optimize import JoinAlgorithmEnum
from app.services.optimizer.models import PhysicalPlanNode
from app.services.optimizer.join_graph import JoinGraph
from app.services.optimizer.cost_model import PAGE_IO_COST, CPU_TUPLE_COST, CPU_INDEX_TUPLE_COST, calculate_join_cost


def solve_greedy(graph: JoinGraph) -> Tuple[PhysicalPlanNode, int]:
    """
    Greedy minimum-selectivity join algorithm using a Min-Heap Priority Queue in O(N^2 log N).
    """
    N = len(graph.tables)
    active_clusters: Dict[int, PhysicalPlanNode] = {}
    subsets_evaluated = 0
    entry_counter = 0

    # 1. Base cluster creation
    for i in range(N):
        alias = graph.tables[i]
        card = graph.get_table_cardinality(alias)
        pages = graph.get_table_pages(alias)
        is_idx, _ = graph.is_table_indexed_for_query(alias)
        if is_idx:
            op = JoinAlgorithmEnum.INDEX_SCAN
            pages_est = max(1.0, math.ceil(math.log2(max(pages, 2.0))))
            cost = pages_est * PAGE_IO_COST + card * CPU_INDEX_TUPLE_COST
        else:
            op = JoinAlgorithmEnum.TABLE_SCAN
            cost = pages * PAGE_IO_COST + card * CPU_TUPLE_COST

        active_clusters[i] = PhysicalPlanNode(
            operator=op,
            cardinality=card,
            cost=cost,
            tables_mask=1 << i,
            table_name=graph.alias_to_table.get(alias, alias),
            alias=alias,
        )
        subsets_evaluated += 1

    # 2. Priority Queue initialized with all pairwise join candidates
    pq: List[Tuple[float, int, int, int, PhysicalPlanNode]] = []
    
    for i in range(N):
        for j in range(i + 1, N):
            subsets_evaluated += 1
            p1 = active_clusters[i]
            p2 = active_clusters[j]
            aliases1 = [graph.tables[k] for k in range(N) if (p1.tables_mask & (1 << k))]
            aliases2 = [graph.tables[k] for k in range(N) if (p2.tables_mask & (1 << k))]
            edges = graph.find_connecting_edges(aliases1, aliases2)
            sel = graph.compute_join_selectivity(edges, p1.cardinality, p2.cardinality)
            best_op, out_card, cost = calculate_join_cost(p1, p2, edges, sel)
            pred_str = " AND ".join(e.raw_predicate for e in edges) if edges else "CROSS JOIN"
            cand = PhysicalPlanNode(
                operator=best_op,
                cardinality=out_card,
                cost=cost,
                tables_mask=p1.tables_mask | p2.tables_mask,
                join_predicate=pred_str,
                left_child=p1,
                right_child=p2,
            )
            heapq.heappush(pq, (cost, entry_counter, i, j, cand))
            entry_counter += 1

    next_cluster_id = N

    # 3. Iterative greedy merge using heap
    while len(active_clusters) > 1 and pq:
        cost, _, c1, c2, cand = heapq.heappop(pq)
        
        if c1 not in active_clusters or c2 not in active_clusters:
            continue

        del active_clusters[c1]
        del active_clusters[c2]

        new_cid = next_cluster_id
        next_cluster_id += 1
        active_clusters[new_cid] = cand

        cand_aliases = [graph.tables[k] for k in range(N) if (cand.tables_mask & (1 << k))]
        for other_cid, other_node in list(active_clusters.items()):
            if other_cid == new_cid:
                continue
            subsets_evaluated += 1
            other_aliases = [graph.tables[k] for k in range(N) if (other_node.tables_mask & (1 << k))]
            edges = graph.find_connecting_edges(cand_aliases, other_aliases)
            sel = graph.compute_join_selectivity(edges, cand.cardinality, other_node.cardinality)
            best_op, out_card, pair_cost = calculate_join_cost(cand, other_node, edges, sel)
            pred_str = " AND ".join(e.raw_predicate for e in edges) if edges else "CROSS JOIN"
            new_cand = PhysicalPlanNode(
                operator=best_op,
                cardinality=out_card,
                cost=pair_cost,
                tables_mask=cand.tables_mask | other_node.tables_mask,
                join_predicate=pred_str,
                left_child=cand,
                right_child=other_node,
            )
            heapq.heappush(pq, (pair_cost, entry_counter, new_cid, other_cid, new_cand))
            entry_counter += 1

    while len(active_clusters) > 1:
        c_ids = list(active_clusters.keys())
        c1, c2 = c_ids[0], c_ids[1]
        p1 = active_clusters.pop(c1)
        p2 = active_clusters.pop(c2)
        sel = graph.compute_join_selectivity([], p1.cardinality, p2.cardinality)
        best_op, out_card, cost = calculate_join_cost(p1, p2, [], sel)
        merged = PhysicalPlanNode(
            operator=best_op,
            cardinality=out_card,
            cost=cost,
            tables_mask=p1.tables_mask | p2.tables_mask,
            join_predicate="CROSS JOIN",
            left_child=p1,
            right_child=p2,
        )
        active_clusters[next_cluster_id] = merged
        next_cluster_id += 1

    root_node = next(iter(active_clusters.values()))
    return root_node, subsets_evaluated


def compute_naive_left_deep(graph: JoinGraph) -> PhysicalPlanNode:
    """
    Computes the naive left-deep join plan in textual order of table declarations.
    """
    N = len(graph.tables)
    alias0 = graph.tables[0]
    card0 = graph.get_table_cardinality(alias0)
    pages0 = graph.get_table_pages(alias0)
    curr = PhysicalPlanNode(
        operator=JoinAlgorithmEnum.TABLE_SCAN,
        cardinality=card0,
        cost=pages0 * PAGE_IO_COST + card0 * CPU_TUPLE_COST,
        tables_mask=1,
        table_name=graph.alias_to_table.get(alias0, alias0),
        alias=alias0,
    )

    accum_mask = 1
    for i in range(1, N):
        next_alias = graph.tables[i]
        next_card = graph.get_table_cardinality(next_alias)
        next_pages = graph.get_table_pages(next_alias)
        next_node = PhysicalPlanNode(
            operator=JoinAlgorithmEnum.TABLE_SCAN,
            cardinality=next_card,
            cost=next_pages * PAGE_IO_COST + next_card * CPU_TUPLE_COST,
            tables_mask=1 << i,
            table_name=graph.alias_to_table.get(next_alias, next_alias),
            alias=next_alias,
        )

        accum_mask |= (1 << i)
        aliases1 = [graph.tables[k] for k in range(N) if (curr.tables_mask & (1 << k))]
        edges = graph.find_connecting_edges(aliases1, [next_alias])
        sel = graph.compute_join_selectivity(edges, curr.cardinality, next_node.cardinality)
        best_op, out_card, cost = calculate_join_cost(curr, next_node, edges, sel)
        pred_str = " AND ".join(e.raw_predicate for e in edges) if edges else "CROSS JOIN"

        curr = PhysicalPlanNode(
            operator=best_op,
            cardinality=out_card,
            cost=cost,
            tables_mask=accum_mask,
            join_predicate=pred_str,
            left_child=curr,
            right_child=next_node,
        )

    return curr

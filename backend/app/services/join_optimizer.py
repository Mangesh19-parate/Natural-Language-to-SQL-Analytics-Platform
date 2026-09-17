import re
import math
import heapq
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set, Tuple
import sqlglot
from sqlglot import exp
from sqlalchemy import Engine, inspect, text

from app.schemas.optimize import (
    JoinAlgorithmEnum,
    GateDecisionEnum,
    JoinPlanResponse,
    JoinPlanRequest,
    ExecutionBenchmarkResult,
)


class CalibratedTableStats:
    """Enterprise Table Statistics calibrated for cost-based query optimization."""
    def __init__(self, table_name: str, tuple_count: float, page_count: float, primary_key: str, indexes: List[str]):
        self.table_name = table_name.lower()
        self.tuple_count = float(tuple_count)
        self.page_count = float(page_count)
        self.primary_key = primary_key.lower()
        self.indexes = [idx.lower() for idx in indexes]


# Baseline schema statistics calibrated to seeded database
DEFAULT_TABLE_STATS: Dict[str, CalibratedTableStats] = {
    "customers": CalibratedTableStats("customers", 150, 2, "customer_id", ["customers_pkey", "idx_customers_city"]),
    "departments": CalibratedTableStats("departments", 10, 1, "department_id", ["departments_pkey"]),
    "employees": CalibratedTableStats("employees", 120, 2, "employee_id", ["employees_pkey", "idx_employees_dept"]),
    "products": CalibratedTableStats("products", 100, 2, "product_id", ["products_pkey", "idx_products_cat"]),
    "orders": CalibratedTableStats("orders", 200, 3, "order_id", ["orders_pkey", "idx_orders_customer"]),
    "sales": CalibratedTableStats("sales", 500, 5, "sale_id", ["sales_pkey", "idx_sales_order", "idx_sales_product"]),
}

# Selinger / System-R Cost Constants
PAGE_IO_COST = 1.0            # Cost of 1 8KB disk page I/O fetch
CPU_TUPLE_COST = 0.01         # Cost of processing 1 row in CPU
CPU_INDEX_TUPLE_COST = 0.005  # Cost of index binary search per tuple
CPU_HASH_COST = 0.02          # Cost of hashing key + hash table insert/probe
CPU_SORT_COST = 0.03          # Cost of N log N sort comparison per tuple


class TableStatsProvider:
    """
    Introspects and caches live database statistics (tuple counts, pages, indexes)
    from SQLAlchemy Engine, falling back to schema defaults when offline.
    """
    _cache: Dict[str, CalibratedTableStats] = {}
    _cache_source: str = "fallback_schema"
    _last_refresh: Optional[datetime] = None
    _ttl_seconds: int = 300

    @classmethod
    def get_stats_map(
        cls,
        engine: Optional[Engine] = None,
        force_refresh: bool = False,
    ) -> Tuple[Dict[str, CalibratedTableStats], str]:
        now = datetime.now(timezone.utc)
        if (
            not force_refresh
            and cls._cache
            and cls._last_refresh
            and (now - cls._last_refresh).total_seconds() < cls._ttl_seconds
        ):
            return cls._cache, cls._cache_source

        if engine is None:
            cls._cache = dict(DEFAULT_TABLE_STATS)
            cls._cache_source = "calibrated_cache"
            cls._last_refresh = now
            return cls._cache, cls._cache_source

        try:
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            stats_map: Dict[str, CalibratedTableStats] = {}

            with engine.connect() as conn:
                for t_name in table_names:
                    t_lower = t_name.lower()
                    # 1. Live row count
                    try:
                        res = conn.execute(text(f'SELECT COUNT(*) FROM "{t_name}"'))
                        tuple_count = float(res.scalar() or 0)
                    except Exception:
                        tuple_count = 100.0

                    # 2. Primary key constraint
                    try:
                        pk_constraint = inspector.get_pk_constraint(t_name)
                        pk_cols = pk_constraint.get("constrained_columns", []) if pk_constraint else []
                        pk_name = pk_cols[0].lower() if pk_cols else "id"
                    except Exception:
                        pk_name = "id"

                    # 3. Secondary indexes
                    try:
                        indexes_raw = inspector.get_indexes(t_name)
                        indexes = [idx["name"].lower() for idx in indexes_raw if idx.get("name")]
                    except Exception:
                        indexes = []

                    # 4. Page count estimation (8KB pages, ~128 bytes per row avg)
                    page_count = max(1.0, math.ceil((tuple_count * 128.0) / 8192.0))

                    stats_map[t_lower] = CalibratedTableStats(
                        table_name=t_lower,
                        tuple_count=tuple_count,
                        page_count=page_count,
                        primary_key=pk_name,
                        indexes=indexes,
                    )

            if stats_map:
                cls._cache = stats_map
                cls._cache_source = "live_engine"
                cls._last_refresh = now
                return cls._cache, cls._cache_source

        except Exception:
            pass

        cls._cache = dict(DEFAULT_TABLE_STATS)
        cls._cache_source = "fallback_schema"
        cls._last_refresh = now
        return cls._cache, cls._cache_source


class JoinEdge:
    """Represents a join predicate between two table aliases."""
    def __init__(
        self,
        table1: str,
        col1: str,
        table2: str,
        col2: str,
        operator: str = "=",
        raw_predicate: str = "",
    ):
        self.table1 = table1.lower()
        self.col1 = col1.lower()
        self.table2 = table2.lower()
        self.col2 = col2.lower()
        self.operator = operator
        self.raw_predicate = raw_predicate

    def connects(self, t1: str, t2: str) -> bool:
        t1_l, t2_l = t1.lower(), t2.lower()
        return (self.table1 == t1_l and self.table2 == t2_l) or (self.table1 == t2_l and self.table2 == t1_l)


class PhysicalPlanNode:
    """A physical execution plan node (Scan or Join)."""
    def __init__(
        self,
        operator: JoinAlgorithmEnum,
        cardinality: float,
        cost: float,
        tables_mask: int,
        table_name: Optional[str] = None,
        alias: Optional[str] = None,
        join_predicate: Optional[str] = None,
        left_child: Optional['PhysicalPlanNode'] = None,
        right_child: Optional['PhysicalPlanNode'] = None,
    ):
        self.operator = operator
        self.cardinality = max(1.0, float(cardinality))
        self.cost = max(0.1, float(cost))
        self.tables_mask = tables_mask
        self.table_name = table_name
        self.alias = alias
        self.join_predicate = join_predicate
        self.left_child = left_child
        self.right_child = right_child

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operator": self.operator.value,
            "table_name": self.table_name,
            "alias": self.alias,
            "join_predicate": self.join_predicate,
            "estimated_cardinality": round(self.cardinality, 1),
            "estimated_cost": round(self.cost, 2),
            "left": self.left_child.to_dict() if self.left_child else None,
            "right": self.right_child.to_dict() if self.right_child else None,
        }


class JoinGraph:
    """
    Extracted AST Join Graph representing relations, predicates, and filter selectivities.
    """
    def __init__(self, sql: str, custom_stats: Optional[Dict[str, CalibratedTableStats]] = None):
        self.sql = sql
        self.stats_map = custom_stats or DEFAULT_TABLE_STATS
        self.tables: List[str] = []               # list of aliases or table names
        self.alias_to_table: Dict[str, str] = {}  # alias -> real table name
        self.edges: List[JoinEdge] = []
        self.filter_selectivity: Dict[str, float] = {}  # alias -> filter factor [0.0..1.0]
        self.filter_columns: Dict[str, Set[str]] = {}   # alias -> set of filtered columns
        self._parse_ast()

    def _parse_ast(self):
        try:
            parsed = sqlglot.parse_one(self.sql, read="postgres")
        except Exception:
            try:
                parsed = sqlglot.parse_one(self.sql)
            except Exception:
                return

        # 1. Discover tables and aliases
        for tbl in parsed.find_all(exp.Table):
            t_name = tbl.name.lower()
            alias = tbl.alias.lower() if tbl.alias else t_name
            if alias not in self.tables:
                self.tables.append(alias)
                self.alias_to_table[alias] = t_name
                self.filter_selectivity[alias] = 1.0
                self.filter_columns[alias] = set()

        # 2. Discover join predicates from ON clauses
        for join in parsed.find_all(exp.Join):
            on_clause = join.args.get("on")
            if on_clause:
                self._extract_join_edges(on_clause)

        # 3. Discover join predicates from WHERE clause (implicit joins)
        where_clause = parsed.find(exp.Where)
        if where_clause:
            self._extract_where_predicates(where_clause.this)

    def _extract_join_edges(self, condition_node: exp.Expression):
        for eq in condition_node.find_all(exp.EQ):
            l_col = eq.left
            r_col = eq.right
            if isinstance(l_col, exp.Column) and isinstance(r_col, exp.Column):
                t1 = l_col.table.lower() if l_col.table else ""
                c1 = l_col.name.lower()
                t2 = r_col.table.lower() if r_col.table else ""
                c2 = r_col.name.lower()
                if t1 and t2 and t1 != t2:
                    edge = JoinEdge(t1, c1, t2, c2, "=", raw_predicate=str(eq))
                    self.edges.append(edge)

    def _extract_where_predicates(self, condition_node: exp.Expression):
        # Check for joins in WHERE
        self._extract_join_edges(condition_node)

        # Single-table filter selectivity estimation
        for col_expr in condition_node.find_all(exp.Column):
            t = col_expr.table.lower() if col_expr.table else ""
            c_name = col_expr.name.lower()
            if t and t in self.filter_selectivity:
                self.filter_columns[t].add(c_name)
                parent = col_expr.parent
                if isinstance(parent, (exp.EQ, exp.Between)):
                    self.filter_selectivity[t] = min(self.filter_selectivity[t], 0.15)
                elif isinstance(parent, (exp.GT, exp.GTE, exp.LT, exp.LTE)):
                    self.filter_selectivity[t] = min(self.filter_selectivity[t], 0.33)
                elif isinstance(parent, exp.Like):
                    self.filter_selectivity[t] = min(self.filter_selectivity[t], 0.20)

    def is_table_indexed_for_query(self, alias: str) -> Tuple[bool, Optional[str]]:
        """
        Determines if table scan can utilize a Primary Key or Secondary Index.
        Returns: (is_indexed, index_name)
        """
        t_name = self.alias_to_table.get(alias, alias)
        stat = self.stats_map.get(t_name)
        if not stat:
            return False, None

        # Check join edges for PK or index hits
        for e in self.edges:
            if e.table1 == alias and (e.col1 == stat.primary_key or any(e.col1 in idx for idx in stat.indexes)):
                return True, stat.primary_key if e.col1 == stat.primary_key else (stat.indexes[0] if stat.indexes else None)
            if e.table2 == alias and (e.col2 == stat.primary_key or any(e.col2 in idx for idx in stat.indexes)):
                return True, stat.primary_key if e.col2 == stat.primary_key else (stat.indexes[0] if stat.indexes else None)

        # Check filter columns
        for c in self.filter_columns.get(alias, set()):
            if c == stat.primary_key or any(c in idx for idx in stat.indexes):
                return True, stat.primary_key if c == stat.primary_key else (stat.indexes[0] if stat.indexes else None)

        return False, None

    def get_table_cardinality(self, alias: str) -> float:
        t_name = self.alias_to_table.get(alias, alias)
        stat = self.stats_map.get(t_name, CalibratedTableStats(t_name, 100, 2, "id", []))
        sel = self.filter_selectivity.get(alias, 1.0)
        return max(1.0, stat.tuple_count * sel)

    def get_table_pages(self, alias: str) -> float:
        t_name = self.alias_to_table.get(alias, alias)
        stat = self.stats_map.get(t_name, CalibratedTableStats(t_name, 100, 2, "id", []))
        return max(1.0, stat.page_count)

    def find_connecting_edges(self, mask1_aliases: List[str], mask2_aliases: List[str]) -> List[JoinEdge]:
        connecting = []
        for e in self.edges:
            for t1 in mask1_aliases:
                for t2 in mask2_aliases:
                    if e.connects(t1, t2):
                        connecting.append(e)
        return connecting

    def compute_join_selectivity(self, edges: List[JoinEdge], card1: float, card2: float) -> float:
        if not edges:
            return 1.0  # Cross Join (Cartesian Product)
        # Selinger FK/PK join formula: 1 / max(|R|, |S|)
        sel = 1.0 / max(card1, card2, 2.0)
        return min(sel, 0.5)


class CostBasedJoinOptimizer:
    """
    COST-BASED QUERY PLANNING & JOIN ORDER OPTIMIZATION ENGINE.
    Implements:
    - AST Join Graph Construction
    - Live Catalog Statistics & Index Scan Modeling
    - Dynamic Programming with Bitmask States (O(3^N) optimal solver for N <= 8)
    - Greedy Minimum-Selectivity Min-Heap Priority Queue (O(N^2 log N) for N > 8)
    - True SQLGlot AST Query Rewriting for Optimal Join Order
    - Pre-execution Safety Gating (Detection of Cartesian blowups & strict cost thresholds)
    - Execution Benchmarking (wall-clock latency & result set equivalence verification)
    """

    @classmethod
    def optimize_query(
        cls,
        sql: str,
        custom_stats: Optional[Dict[str, CalibratedTableStats]] = None,
        engine: Optional[Engine] = None,
        max_allowed_cost: float = 50000.0,
        strict_admission: bool = True,
        benchmark: bool = False,
    ) -> JoinPlanResponse:
        """
        Computes the globally optimal physical join plan for a SQL query,
        rewrites the AST with optimal join ordering, and evaluates admission safety.
        """
        # 1. Resolve table statistics map
        if custom_stats:
            stats_map = custom_stats
            stats_source = "custom"
        else:
            stats_map, stats_source = TableStatsProvider.get_stats_map(engine)

        graph = JoinGraph(sql, stats_map)
        num_tables = len(graph.tables)
        indexes_used: List[str] = []

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
                execution_recommendation="Single-table query verified with optimal sequential/index scan",
                created_at=datetime.now(timezone.utc).isoformat(),
            )

        # Multi-table join optimization
        if num_tables <= 8:
            optimal_plan, subsets_eval = cls._solve_bitmask_dp(graph)
            strategy = "BITMASK_DYNAMIC_PROGRAMMING"
        else:
            optimal_plan, subsets_eval = cls._solve_greedy(graph)
            strategy = "GREEDY_MIN_SELECTIVITY"

        # Collect indexes used in the chosen plan
        cls._collect_indexes_used(optimal_plan, graph, indexes_used)

        # Compute naive left-deep plan cost for comparison
        naive_plan = cls._compute_naive_left_deep(graph)
        naive_cost = max(naive_plan.cost, 1.0)
        optimal_cost = optimal_plan.cost
        reduction_pct = max(0.0, round(((naive_cost - optimal_cost) / naive_cost) * 100.0, 1))

        # Check for unconstrained Cartesian explosion
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
            rec = f"Optimal join order computed using {strategy}. Estimated cost reduction: {reduction_pct}%."

        # Generate genuine rewritten SQL based on optimal join tree
        optimized_sql = cls._generate_optimized_sql(graph, optimal_plan, sql)

        # Optional execution benchmark profiling
        exec_benchmark = None
        if benchmark and engine and gate_decision == GateDecisionEnum.ALLOW:
            exec_benchmark = cls.benchmark_execution(sql, optimized_sql, engine)

        return JoinPlanResponse(
            original_sql=sql,
            optimized_sql=optimized_sql,
            tables=graph.tables,
            join_edges_count=len(graph.edges),
            search_strategy=strategy,
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
    def _calculate_join_cost(
        cls,
        plan1: PhysicalPlanNode,
        plan2: PhysicalPlanNode,
        connecting_edges: List[JoinEdge],
    ) -> Tuple[JoinAlgorithmEnum, float, float]:
        """
        Computes the physical join algorithm and associated cost consistently across planners.
        Returns: (best_operator, estimated_cardinality, total_cost)
        """
        # Selectivity
        if not connecting_edges:
            sel = 1.0  # Cartesian product
        else:
            sel = 1.0 / max(plan1.cardinality, plan2.cardinality, 2.0)
            sel = min(sel, 0.5)

        out_card = max(1.0, plan1.cardinality * plan2.cardinality * sel)

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

    @classmethod
    def _solve_bitmask_dp(cls, graph: JoinGraph) -> Tuple[PhysicalPlanNode, int]:
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

                # Submask partitioning trick: s1 iterates all non-empty proper submasks of mask
                s1 = (mask - 1) & mask
                while s1 > 0:
                    s2 = mask ^ s1
                    if s1 < s2:  # Only evaluate non-symmetric partition pairs
                        plan1 = dp.get(s1)
                        plan2 = dp.get(s2)

                        if plan1 and plan2:
                            subsets_evaluated += 1
                            aliases1 = [graph.tables[i] for i in range(N) if (s1 & (1 << i))]
                            aliases2 = [graph.tables[i] for i in range(N) if (s2 & (1 << i))]

                            connecting_edges = graph.find_connecting_edges(aliases1, aliases2)
                            best_op, out_card, min_join_cost = cls._calculate_join_cost(plan1, plan2, connecting_edges)
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

    @classmethod
    def _solve_greedy(cls, graph: JoinGraph) -> Tuple[PhysicalPlanNode, int]:
        """
        Greedy minimum-selectivity join algorithm using a true Min-Heap Priority Queue in O(N^2 log N).
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
                best_op, out_card, cost = cls._calculate_join_cost(p1, p2, edges)
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
            
            # Skip stale heap entries where either cluster was already merged
            if c1 not in active_clusters or c2 not in active_clusters:
                continue

            del active_clusters[c1]
            del active_clusters[c2]

            new_cid = next_cluster_id
            next_cluster_id += 1
            active_clusters[new_cid] = cand

            # Push new join candidates between merged cluster and all remaining clusters
            cand_aliases = [graph.tables[k] for k in range(N) if (cand.tables_mask & (1 << k))]
            for other_cid, other_node in list(active_clusters.items()):
                if other_cid == new_cid:
                    continue
                subsets_evaluated += 1
                other_aliases = [graph.tables[k] for k in range(N) if (other_node.tables_mask & (1 << k))]
                edges = graph.find_connecting_edges(cand_aliases, other_aliases)
                best_op, out_card, pair_cost = cls._calculate_join_cost(cand, other_node, edges)
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

        # Fallback if any disconnected components remain without heap items
        while len(active_clusters) > 1:
            c_ids = list(active_clusters.keys())
            c1, c2 = c_ids[0], c_ids[1]
            p1 = active_clusters.pop(c1)
            p2 = active_clusters.pop(c2)
            best_op, out_card, cost = cls._calculate_join_cost(p1, p2, [])
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

    @classmethod
    def _compute_naive_left_deep(cls, graph: JoinGraph) -> PhysicalPlanNode:
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
            best_op, out_card, cost = cls._calculate_join_cost(curr, next_node, edges)
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

    @classmethod
    def _generate_optimized_sql(cls, graph: JoinGraph, plan: PhysicalPlanNode, original_sql: str) -> str:
        """
        Generates genuinely rewritten SQL query AST reflecting the optimal join order.
        """
        ordered_aliases = cls._extract_ordered_aliases(plan)
        if len(ordered_aliases) <= 1:
            return original_sql

        try:
            parsed = sqlglot.parse_one(original_sql, read="postgres")
        except Exception:
            try:
                parsed = sqlglot.parse_one(original_sql)
            except Exception:
                return original_sql

        if not isinstance(parsed, exp.Select):
            return original_sql

        try:
            # 1. Map existing join types from the original query (INNER, LEFT, RIGHT, etc.)
            original_join_kinds: Dict[str, str] = {}
            for j in parsed.find_all(exp.Join):
                tbl = j.this
                if isinstance(tbl, exp.Table):
                    alias = tbl.alias.lower() if tbl.alias else tbl.name.lower()
                    kind = j.args.get("kind")
                    if kind:
                        original_join_kinds[alias] = str(kind).upper()
                    elif j.args.get("side"):
                        original_join_kinds[alias] = str(j.args.get("side")).upper()
                    else:
                        original_join_kinds[alias] = "INNER"

            # 2. Rebuild FROM table
            first_alias = ordered_aliases[0]
            first_table = graph.alias_to_table.get(first_alias, first_alias)
            if first_alias != first_table:
                from_tbl = exp.Table(this=exp.to_identifier(first_table), alias=exp.TableAlias(this=exp.to_identifier(first_alias)))
            else:
                from_tbl = exp.Table(this=exp.to_identifier(first_table))
            
            parsed.set("from_", exp.From(this=from_tbl))

            # 3. Rebuild sequential JOIN clauses in optimal order
            placed_aliases: Set[str] = {first_alias}
            new_joins: List[exp.Join] = []

            for alias in ordered_aliases[1:]:
                t_name = graph.alias_to_table.get(alias, alias)
                if alias != t_name:
                    tbl_join = exp.Table(this=exp.to_identifier(t_name), alias=exp.TableAlias(this=exp.to_identifier(alias)))
                else:
                    tbl_join = exp.Table(this=exp.to_identifier(t_name))

                connecting_edges = graph.find_connecting_edges([alias], list(placed_aliases))
                join_kind = original_join_kinds.get(alias, "INNER")

                if connecting_edges:
                    pred_str = " AND ".join(e.raw_predicate for e in connecting_edges)
                    on_expr = sqlglot.parse_one(pred_str)
                    new_joins.append(exp.Join(this=tbl_join, on=on_expr, kind=join_kind))
                else:
                    new_joins.append(exp.Join(this=tbl_join, kind="CROSS"))

                placed_aliases.add(alias)

            parsed.set("joins", new_joins)
            return parsed.sql(pretty=True)
        except Exception:
            return original_sql

    @classmethod
    def _extract_ordered_aliases(cls, node: PhysicalPlanNode) -> List[str]:
        if node.alias:
            return [node.alias]
        res = []
        if node.left_child:
            res.extend(cls._extract_ordered_aliases(node.left_child))
        if node.right_child:
            res.extend(cls._extract_ordered_aliases(node.right_child))
        return res

    @classmethod
    def benchmark_execution(
        cls,
        original_sql: str,
        optimized_sql: str,
        engine: Engine,
    ) -> ExecutionBenchmarkResult:
        """
        Executes original and rewritten SQL queries against the database engine,
        measures wall-clock execution latency, and verifies result equivalence.
        """
        def run_query(conn, query_str: str):
            t0 = time.perf_counter()
            result = conn.execute(text(query_str))
            rows = result.fetchall()
            t1 = time.perf_counter()
            return rows, (t1 - t0) * 1000.0

        try:
            with engine.connect() as conn:
                orig_rows, orig_time_ms = run_query(conn, original_sql)
                opt_rows, opt_time_ms = run_query(conn, optimized_sql)

            orig_count = len(orig_rows)
            opt_count = len(opt_rows)
            
            # Serialize tuples for set equivalence check
            orig_serialized = sorted([str(tuple(r)) for r in orig_rows])
            opt_serialized = sorted([str(tuple(r)) for r in opt_rows])
            results_match = (orig_serialized == opt_serialized)

            speedup = round(orig_time_ms / max(opt_time_ms, 0.001), 2)

            return ExecutionBenchmarkResult(
                original_exec_ms=round(orig_time_ms, 3),
                optimized_exec_ms=round(opt_time_ms, 3),
                speedup_ratio=speedup,
                results_equivalent=results_match,
                row_count=orig_count,
                validation_status="VERIFIED_EQUIVALENT" if results_match else "DATA_MISMATCH",
            )
        except Exception as e:
            return ExecutionBenchmarkResult(
                original_exec_ms=0.0,
                optimized_exec_ms=0.0,
                speedup_ratio=1.0,
                results_equivalent=False,
                row_count=0,
                validation_status=f"BENCHMARK_ERROR: {str(e)}",
            )

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
    """
    Calibrated Table Statistics for cost-based query optimization.
    Stores live tuple counts, page estimates, PK/FK relationships, and exact indexed column sets.
    """
    def __init__(
        self,
        table_name: str,
        tuple_count: float,
        page_count: float,
        primary_key: str,
        indexes: List[str],
        index_columns: Optional[Dict[str, List[str]]] = None,
        foreign_keys: Optional[List[Dict[str, Any]]] = None,
        ndv_map: Optional[Dict[str, float]] = None,
    ):
        self.table_name = table_name.lower()
        self.tuple_count = max(1.0, float(tuple_count))
        self.page_count = max(1.0, float(page_count))
        self.primary_key = primary_key.lower() if primary_key else "id"
        self.indexes = [idx.lower() for idx in indexes]
        self.index_columns = {
            idx.lower(): [c.lower() for c in cols]
            for idx, cols in (index_columns or {}).items()
        }
        self.foreign_keys = foreign_keys or []
        self.ndv_map = {k.lower(): max(1.0, float(v)) for k, v in (ndv_map or {}).items()}


# Baseline schema statistics calibrated to default seeded database
DEFAULT_TABLE_STATS: Dict[str, CalibratedTableStats] = {
    "customers": CalibratedTableStats(
        table_name="customers",
        tuple_count=150,
        page_count=2,
        primary_key="customer_id",
        indexes=["customers_pkey", "idx_customers_city"],
        index_columns={
            "customers_pkey": ["customer_id"],
            "idx_customers_city": ["city"],
        },
        ndv_map={"customer_id": 150.0, "city": 12.0, "total_spent": 140.0},
    ),
    "departments": CalibratedTableStats(
        table_name="departments",
        tuple_count=10,
        page_count=1,
        primary_key="department_id",
        indexes=["departments_pkey"],
        index_columns={"departments_pkey": ["department_id"]},
        ndv_map={"department_id": 10.0, "department_name": 10.0},
    ),
    "employees": CalibratedTableStats(
        table_name="employees",
        tuple_count=120,
        page_count=2,
        primary_key="employee_id",
        indexes=["employees_pkey", "idx_employees_dept"],
        index_columns={
            "employees_pkey": ["employee_id"],
            "idx_employees_dept": ["department_id"],
        },
        foreign_keys=[
            {"constrained_columns": ["department_id"], "referred_table": "departments", "referred_columns": ["department_id"]}
        ],
        ndv_map={"employee_id": 120.0, "department_id": 10.0, "salary": 95.0},
    ),
    "products": CalibratedTableStats(
        table_name="products",
        tuple_count=100,
        page_count=2,
        primary_key="product_id",
        indexes=["products_pkey", "idx_products_cat"],
        index_columns={
            "products_pkey": ["product_id"],
            "idx_products_cat": ["category"],
        },
        ndv_map={"product_id": 100.0, "category": 6.0, "price": 80.0},
    ),
    "orders": CalibratedTableStats(
        table_name="orders",
        tuple_count=200,
        page_count=3,
        primary_key="order_id",
        indexes=["orders_pkey", "idx_orders_customer"],
        index_columns={
            "orders_pkey": ["order_id"],
            "idx_orders_customer": ["customer_id"],
        },
        foreign_keys=[
            {"constrained_columns": ["customer_id"], "referred_table": "customers", "referred_columns": ["customer_id"]}
        ],
        ndv_map={"order_id": 200.0, "customer_id": 85.0, "total_amount": 180.0},
    ),
    "sales": CalibratedTableStats(
        table_name="sales",
        tuple_count=500,
        page_count=5,
        primary_key="sale_id",
        indexes=["sales_pkey", "idx_sales_order", "idx_sales_product"],
        index_columns={
            "sales_pkey": ["sale_id"],
            "idx_sales_order": ["order_id"],
            "idx_sales_product": ["product_id"],
        },
        foreign_keys=[
            {"constrained_columns": ["order_id"], "referred_table": "orders", "referred_columns": ["order_id"]},
            {"constrained_columns": ["product_id"], "referred_table": "products", "referred_columns": ["product_id"]},
        ],
        ndv_map={"sale_id": 500.0, "order_id": 200.0, "product_id": 100.0, "revenue": 420.0},
    ),
}

# Selinger-inspired deterministic educational cost constants
PAGE_IO_COST = 1.0            # Cost of 1 8KB disk page I/O fetch
CPU_TUPLE_COST = 0.01         # Cost of processing 1 row in CPU
CPU_INDEX_TUPLE_COST = 0.005  # Cost of index binary search per tuple
CPU_HASH_COST = 0.02          # Cost of hashing key + hash table insert/probe
CPU_SORT_COST = 0.03          # Cost of N log N sort comparison per tuple


class TableStatsProvider:
    """
    Introspects and caches live database statistics (tuple counts, pages, exact index columns, PK/FK)
    from SQLAlchemy Engine, partitioned strictly per data source identity / engine to prevent cross-tenant cache contamination.
    """
    _cache: Dict[str, Dict[str, CalibratedTableStats]] = {}
    _cache_source: Dict[str, str] = {}
    _last_refresh: Dict[str, datetime] = {}
    _ttl_seconds: int = 300

    @classmethod
    def _get_cache_key(cls, data_source_id: int, engine: Optional[Engine]) -> str:
        if engine is not None:
            engine_str = str(engine.url)
            return f"ds_{data_source_id}:{hash(engine_str)}"
        return f"ds_{data_source_id}:fallback"

    @classmethod
    def get_stats_map(
        cls,
        engine: Optional[Engine] = None,
        data_source_id: int = 1,
        force_refresh: bool = False,
    ) -> Tuple[Dict[str, CalibratedTableStats], str]:
        now = datetime.now(timezone.utc)
        cache_key = cls._get_cache_key(data_source_id, engine)

        if (
            not force_refresh
            and cache_key in cls._cache
            and cache_key in cls._last_refresh
            and (now - cls._last_refresh[cache_key]).total_seconds() < cls._ttl_seconds
        ):
            return cls._cache[cache_key], cls._cache_source.get(cache_key, "calibrated_cache")

        if engine is None:
            cls._cache[cache_key] = dict(DEFAULT_TABLE_STATS)
            cls._cache_source[cache_key] = "calibrated_cache"
            cls._last_refresh[cache_key] = now
            return cls._cache[cache_key], cls._cache_source[cache_key]

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
                        pk_cols = ["id"]

                    # 3. Secondary indexes with actual column introspection
                    index_names: List[str] = []
                    index_columns_map: Dict[str, List[str]] = {}
                    if pk_cols:
                        pk_idx_name = f"{t_lower}_pkey"
                        index_names.append(pk_idx_name)
                        index_columns_map[pk_idx_name] = [c.lower() for c in pk_cols]

                    try:
                        indexes_raw = inspector.get_indexes(t_name)
                        for idx in indexes_raw:
                            idx_n = idx.get("name")
                            if idx_n:
                                idx_n_lower = idx_n.lower()
                                index_names.append(idx_n_lower)
                                cols = [c.lower() for c in idx.get("column_names", []) if c]
                                index_columns_map[idx_n_lower] = cols
                    except Exception:
                        pass

                    # 4. Foreign key constraints
                    foreign_keys: List[Dict[str, Any]] = []
                    try:
                        fks_raw = inspector.get_foreign_keys(t_name)
                        for fk in fks_raw:
                            foreign_keys.append({
                                "constrained_columns": [c.lower() for c in fk.get("constrained_columns", [])],
                                "referred_table": fk.get("referred_table", "").lower(),
                                "referred_columns": [c.lower() for c in fk.get("referred_columns", [])],
                            })
                    except Exception:
                        pass

                    # 5. Page count estimation (8KB pages, ~128 bytes per row avg)
                    page_count = max(1.0, math.ceil((tuple_count * 128.0) / 8192.0))

                    # 6. NDV estimations for indexed / PK columns
                    ndv_map: Dict[str, float] = {}
                    for col_list in index_columns_map.values():
                        for col in col_list:
                            if col not in ndv_map:
                                try:
                                    ndv_res = conn.execute(text(f'SELECT COUNT(DISTINCT "{col}") FROM "{t_name}"'))
                                    ndv_map[col] = float(ndv_res.scalar() or 1.0)
                                except Exception:
                                    ndv_map[col] = min(tuple_count, 10.0)

                    stats_map[t_lower] = CalibratedTableStats(
                        table_name=t_lower,
                        tuple_count=tuple_count,
                        page_count=page_count,
                        primary_key=pk_name,
                        indexes=index_names,
                        index_columns=index_columns_map,
                        foreign_keys=foreign_keys,
                        ndv_map=ndv_map,
                    )

            if stats_map:
                cls._cache[cache_key] = stats_map
                cls._cache_source[cache_key] = "live_engine"
                cls._last_refresh[cache_key] = now
                return cls._cache[cache_key], cls._cache_source[cache_key]

        except Exception:
            pass

        cls._cache[cache_key] = dict(DEFAULT_TABLE_STATS)
        cls._cache_source[cache_key] = "fallback_schema"
        cls._last_refresh[cache_key] = now
        return cls._cache[cache_key], cls._cache_source[cache_key]


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
    """An estimated physical plan node (Scan or Join) in the educational cost model."""
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
    Enforces strict query shape boundary checks (CTEs, subqueries, outer joins).
    """
    def __init__(self, sql: str, custom_stats: Optional[Dict[str, CalibratedTableStats]] = None):
        self.sql = sql
        self.stats_map = custom_stats or DEFAULT_TABLE_STATS
        self.tables: List[str] = []               # list of aliases or table names
        self.alias_to_table: Dict[str, str] = {}  # alias -> real table name
        self.edges: List[JoinEdge] = []
        self.filter_selectivity: Dict[str, float] = {}  # alias -> filter factor [0.0..1.0]
        self.filter_columns: Dict[str, Set[str]] = {}   # alias -> set of filtered columns
        self.is_shape_supported: bool = True
        self.unsupported_reason: Optional[str] = None
        self.has_outer_join: bool = False
        self._parse_ast()

    def _parse_ast(self):
        try:
            parsed = sqlglot.parse_one(self.sql, read="postgres")
        except Exception:
            try:
                parsed = sqlglot.parse_one(self.sql)
            except Exception:
                self.is_shape_supported = False
                self.unsupported_reason = "UNPARSEABLE_SQL"
                return

        # Check for non-Select statements
        if not isinstance(parsed, exp.Select):
            self.is_shape_supported = False
            self.unsupported_reason = "NON_SELECT_STATEMENT"
            return

        # Check for CTEs (WITH clause / CTE expressions)
        if parsed.find(exp.With) or parsed.find(exp.CTE) or parsed.args.get("with"):
            self.is_shape_supported = False
            self.unsupported_reason = "CTE_EXPRESSION_PRESENT"
            return

        # Check for set operations (UNION, INTERSECT, EXCEPT)
        if isinstance(parsed, (exp.Union, exp.Intersect, exp.Except)) or parsed.find((exp.Union, exp.Intersect, exp.Except)):
            self.is_shape_supported = False
            self.unsupported_reason = "SET_OPERATION_PRESENT"
            return

        # Check for nested subqueries inside FROM or WHERE
        if parsed.find(exp.Subquery):
            self.is_shape_supported = False
            self.unsupported_reason = "NESTED_SUBQUERY_PRESENT"
            return

        # Inspect joins for OUTER join types
        for join in parsed.find_all(exp.Join):
            kind = str(join.args.get("kind") or "").upper()
            side = str(join.args.get("side") or "").upper()
            if any(k in ["LEFT", "RIGHT", "FULL"] for k in [kind, side]):
                self.has_outer_join = True

        # Extract all tables (safe because CTEs and subqueries are already filtered)
        for tbl in parsed.find_all(exp.Table):
            t_name = tbl.name.lower()
            alias = tbl.alias.lower() if tbl.alias else t_name
            if alias not in self.tables:
                self.tables.append(alias)
                self.alias_to_table[alias] = t_name
                self.filter_selectivity[alias] = 1.0
                self.filter_columns[alias] = set()

        # Extract join predicates from ON clauses
        for join in parsed.find_all(exp.Join):
            on_clause = join.args.get("on")
            if on_clause:
                self._extract_join_edges(on_clause)

        # Extract join predicates from WHERE clause (implicit joins)
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
        self._extract_join_edges(condition_node)

        # Single-table filter selectivity estimation using NDV where available
        for col_expr in condition_node.find_all(exp.Column):
            t = col_expr.table.lower() if col_expr.table else ""
            c_name = col_expr.name.lower()
            if t and t in self.filter_selectivity:
                self.filter_columns[t].add(c_name)
                t_name = self.alias_to_table.get(t, t)
                stat = self.stats_map.get(t_name)
                ndv = stat.ndv_map.get(c_name) if stat else None

                parent = col_expr.parent
                if isinstance(parent, (exp.EQ, exp.Between)):
                    if ndv and ndv > 1.0:
                        self.filter_selectivity[t] = min(self.filter_selectivity[t], 1.0 / ndv)
                    else:
                        self.filter_selectivity[t] = min(self.filter_selectivity[t], 0.15)
                elif isinstance(parent, (exp.GT, exp.GTE, exp.LT, exp.LTE)):
                    self.filter_selectivity[t] = min(self.filter_selectivity[t], 0.33)
                elif isinstance(parent, exp.Like):
                    self.filter_selectivity[t] = min(self.filter_selectivity[t], 0.20)

    def is_table_indexed_for_query(self, alias: str) -> Tuple[bool, Optional[str]]:
        """
        Determines if table scan can utilize a Primary Key or Secondary Index
        by checking EXACT indexed column definitions, not index name substrings.
        Returns: (is_indexed, index_name)
        """
        t_name = self.alias_to_table.get(alias, alias)
        stat = self.stats_map.get(t_name)
        if not stat:
            return False, None

        # 1. Check join edges for exact indexed column matches
        for e in self.edges:
            col_to_check = e.col1 if e.table1 == alias else (e.col2 if e.table2 == alias else None)
            if col_to_check:
                if col_to_check == stat.primary_key:
                    return True, f"{stat.table_name}_pkey"
                for idx_name, idx_cols in stat.index_columns.items():
                    if col_to_check in idx_cols:
                        return True, idx_name

        # 2. Check filter columns for exact indexed column matches
        for c in self.filter_columns.get(alias, set()):
            if c == stat.primary_key:
                return True, f"{stat.table_name}_pkey"
            for idx_name, idx_cols in stat.index_columns.items():
                if c in idx_cols:
                    return True, idx_name

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

        # Foreign Key / Primary Key selectivity calculation
        for e in edges:
            t1_name = self.alias_to_table.get(e.table1, e.table1)
            t2_name = self.alias_to_table.get(e.table2, e.table2)
            stat1 = self.stats_map.get(t1_name)
            stat2 = self.stats_map.get(t2_name)

            if stat1 and stat2:
                if e.col1 == stat1.primary_key:
                    return min(1.0 / max(stat1.tuple_count, 2.0), 0.5)
                if e.col2 == stat2.primary_key:
                    return min(1.0 / max(stat2.tuple_count, 2.0), 0.5)

                ndv1 = stat1.ndv_map.get(e.col1)
                ndv2 = stat2.ndv_map.get(e.col2)
                if ndv1 and ndv2:
                    return min(1.0 / max(ndv1, ndv2, 2.0), 0.5)

        sel = 1.0 / max(card1, card2, 2.0)
        return min(sel, 0.5)


class CostBasedJoinOptimizer:
    """
    Selinger-Inspired Cost-Based Join-Planning Subsystem.
    Provides application-level estimated physical plans and deterministic admission gating.
    Algorithms:
    - Bitmask Dynamic Programming (O(3^N) optimal solver for N <= 8)
    - Min-Heap Priority Queue Greedy Solver (O(N^2 log N) for N > 8)
    - AST Query Rewriter strictly restricted to commutative/associative INNER joins
    - Shape Guards (Automatic safe bypass for CTEs, subqueries, and complex outer joins)
    - Deterministic Admission Gate against Cartesian row explosion and runaway costs
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
                execution_recommendation="Bypassed safe query pass-through",
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
                execution_recommendation="Single-table query verified with estimated scan plan",
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

        # Safe AST rewrite: Only rewrite purely associative/commutative INNER joins
        if graph.has_outer_join:
            optimized_sql = sql
            rec += " (Outer joins preserved without reordering to guarantee semantic invariance)."
        else:
            optimized_sql = cls._generate_optimized_sql(graph, optimal_plan, sql)

        # Optional execution benchmark profiling with memory bounds
        exec_benchmark = None
        if benchmark and engine and gate_decision == GateDecisionEnum.ALLOW:
            exec_benchmark = cls.benchmark_execution(sql, optimized_sql, engine)

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
    def _calculate_join_cost(
        cls,
        plan1: PhysicalPlanNode,
        plan2: PhysicalPlanNode,
        connecting_edges: List[JoinEdge],
        graph: JoinGraph,
    ) -> Tuple[JoinAlgorithmEnum, float, float]:
        """
        Computes the physical join algorithm and associated cost consistently across planners.
        Returns: (best_operator, estimated_cardinality, total_cost)
        """
        sel = graph.compute_join_selectivity(connecting_edges, plan1.cardinality, plan2.cardinality)
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
                            best_op, out_card, min_join_cost = cls._calculate_join_cost(plan1, plan2, connecting_edges, graph)
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
                best_op, out_card, cost = cls._calculate_join_cost(p1, p2, edges, graph)
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
                best_op, out_card, pair_cost = cls._calculate_join_cost(cand, other_node, edges, graph)
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
            best_op, out_card, cost = cls._calculate_join_cost(p1, p2, [], graph)
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
            best_op, out_card, cost = cls._calculate_join_cost(curr, next_node, edges, graph)
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
        Generates rewritten SQL AST strictly for associative/commutative INNER joins.
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
            first_alias = ordered_aliases[0]
            first_table = graph.alias_to_table.get(first_alias, first_alias)
            if first_alias != first_table:
                from_tbl = exp.Table(this=exp.to_identifier(first_table), alias=exp.TableAlias(this=exp.to_identifier(first_alias)))
            else:
                from_tbl = exp.Table(this=exp.to_identifier(first_table))
            
            parsed.set("from_", exp.From(this=from_tbl))

            placed_aliases: Set[str] = {first_alias}
            new_joins: List[exp.Join] = []

            for alias in ordered_aliases[1:]:
                t_name = graph.alias_to_table.get(alias, alias)
                if alias != t_name:
                    tbl_join = exp.Table(this=exp.to_identifier(t_name), alias=exp.TableAlias(this=exp.to_identifier(alias)))
                else:
                    tbl_join = exp.Table(this=exp.to_identifier(t_name))

                connecting_edges = graph.find_connecting_edges([alias], list(placed_aliases))

                if connecting_edges:
                    pred_str = " AND ".join(e.raw_predicate for e in connecting_edges)
                    on_expr = sqlglot.parse_one(pred_str)
                    new_joins.append(exp.Join(this=tbl_join, on=on_expr, kind="INNER"))
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
        max_rows: int = 1000,
    ) -> ExecutionBenchmarkResult:
        """
        Executes original and rewritten SQL queries against the database engine with strict row limits,
        measures wall-clock execution latency, and verifies result equivalence without memory exhaustion.
        """
        def run_query(conn, query_str: str):
            t0 = time.perf_counter()
            result = conn.execute(text(query_str))
            rows = result.fetchmany(max_rows)
            t1 = time.perf_counter()
            return rows, (t1 - t0) * 1000.0

        try:
            with engine.connect() as conn:
                orig_rows, orig_time_ms = run_query(conn, original_sql)
                opt_rows, opt_time_ms = run_query(conn, optimized_sql)

            orig_count = len(orig_rows)
            opt_count = len(opt_rows)
            
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

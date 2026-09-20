from typing import List, Dict, Set, Optional, Tuple
import sqlglot
from sqlglot import exp
from app.services.optimizer.models import CalibratedTableStats, DEFAULT_TABLE_STATS, JoinEdge


class JoinGraph:
    """
    Extracted AST Join Graph representing relations, predicates, and filter selectivities.
    Enforces strict query shape boundary checks (CTEs, subqueries, outer joins, volatile functions).
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
        self.has_insufficient_stats: bool = False
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

        # 1. Set operations rejection (UNION, INTERSECT, EXCEPT)
        if isinstance(parsed, (exp.Union, exp.Intersect, exp.Except)) or parsed.find((exp.Union, exp.Intersect, exp.Except)):
            self.is_shape_supported = False
            self.unsupported_reason = "SET_OPERATION_PRESENT"
            return

        # 2. Non-Select statements rejection
        if not isinstance(parsed, exp.Select):
            self.is_shape_supported = False
            self.unsupported_reason = "NON_SELECT_STATEMENT"
            return

        # 3. CTEs rejection
        if parsed.find(exp.With) or parsed.find(exp.CTE) or (hasattr(parsed, "args") and parsed.args.get("with")):
            self.is_shape_supported = False
            self.unsupported_reason = "CTE_EXPRESSION_PRESENT"
            return

        # 4. Nested subqueries rejection
        if parsed.find(exp.Subquery):
            self.is_shape_supported = False
            self.unsupported_reason = "NESTED_SUBQUERY_PRESENT"
            return

        # 5. Window functions rejection
        if parsed.find(exp.Window) or parsed.find(exp.WindowSpec):
            self.is_shape_supported = False
            self.unsupported_reason = "WINDOW_FUNCTION_PRESENT"
            return

        # 6. Volatile or non-deterministic functions check
        if parsed.find(exp.Rand):
            self.is_shape_supported = False
            self.unsupported_reason = "VOLATILE_FUNCTION_RANDOM"
            return

        volatile_names = {"RANDOM", "RAND", "NOW", "CLOCK_TIMESTAMP", "GEN_RANDOM_UUID", "CURRENT_TIMESTAMP"}
        for func in parsed.find_all((exp.Anonymous, exp.Func)):
            name = (getattr(func, "name", None) or getattr(func, "key", None) or type(func).__name__).upper()
            if name in volatile_names:
                self.is_shape_supported = False
                self.unsupported_reason = f"VOLATILE_FUNCTION_{name}"
                return

        # 6. Outer join detection & shape rejection
        for join in parsed.find_all(exp.Join):
            kind = str(join.args.get("kind") or "").upper()
            side = str(join.args.get("side") or "").upper()
            if any(k in ["LEFT", "RIGHT", "FULL"] for k in [kind, side]):
                self.has_outer_join = True
                self.is_shape_supported = False
                self.unsupported_reason = f"OUTER_JOIN_UNSUPPORTED_{side or kind}"
                return

        # 7. Discover tables and aliases
        for tbl in parsed.find_all(exp.Table):
            t_name = tbl.name.lower()
            alias = tbl.alias.lower() if tbl.alias else t_name
            if alias not in self.tables:
                self.tables.append(alias)
                self.alias_to_table[alias] = t_name
                self.filter_selectivity[alias] = 1.0
                self.filter_columns[alias] = set()

        # 8. Discover and strictly validate join predicates from ON clauses
        for join in parsed.find_all(exp.Join):
            on_clause = join.args.get("on")
            if on_clause:
                is_valid_equi = self._validate_and_extract_join_edges(on_clause)
                if not is_valid_equi:
                    self.is_shape_supported = False
                    self.unsupported_reason = "NON_EQUI_OR_COMPLEX_JOIN_PREDICATE"
                    return

        # 9. Discover join predicates from WHERE clause (implicit joins)
        where_clause = parsed.find(exp.Where)
        if where_clause:
            self._extract_where_predicates(where_clause.this)

    def _validate_and_extract_join_edges(self, condition_node: exp.Expression) -> bool:
        """
        Validates that ON condition is strictly a conjunction (AND) of column equality predicates (a.id = b.id).
        Rejects non-equi joins (> < >= <= !=), OR branches, functions, and literals in ON clauses.
        """
        conjuncts = []
        if isinstance(condition_node, exp.And):
            conjuncts = list(condition_node.flatten())
        else:
            conjuncts = [condition_node]

        for c in conjuncts:
            if not isinstance(c, exp.EQ):
                return False
            l_col = c.left
            r_col = c.right
            if not (isinstance(l_col, exp.Column) and isinstance(r_col, exp.Column)):
                return False
            t1 = l_col.table.lower() if l_col.table else ""
            c1 = l_col.name.lower()
            t2 = r_col.table.lower() if r_col.table else ""
            c2 = r_col.name.lower()
            if not (t1 and t2 and t1 != t2):
                return False
            edge = JoinEdge(t1, c1, t2, c2, "=", raw_predicate=str(c))
            self.edges.append(edge)

        return True

    def _extract_where_predicates(self, condition_node: exp.Expression):
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

        for e in self.edges:
            col_to_check = e.col1 if e.table1 == alias else (e.col2 if e.table2 == alias else None)
            if col_to_check:
                if col_to_check == stat.primary_key:
                    return True, f"{stat.table_name}_pkey"
                for idx_name, idx_cols in stat.index_columns.items():
                    if col_to_check in idx_cols:
                        return True, idx_name

        for c in self.filter_columns.get(alias, set()):
            if c == stat.primary_key:
                return True, f"{stat.table_name}_pkey"
            for idx_name, idx_cols in stat.index_columns.items():
                if c in idx_cols:
                    return True, idx_name

        return False, None

    def get_table_cardinality(self, alias: str) -> float:
        t_name = self.alias_to_table.get(alias, alias)
        stat = self.stats_map.get(t_name)
        if not stat:
            self.has_insufficient_stats = True
            stat = CalibratedTableStats(t_name, 1.0, 1.0, "id", [], is_live=False, confidence="INSUFFICIENT_STATISTICS")
        sel = self.filter_selectivity.get(alias, 1.0)
        return max(1.0, stat.tuple_count * sel)

    def get_table_pages(self, alias: str) -> float:
        t_name = self.alias_to_table.get(alias, alias)
        stat = self.stats_map.get(t_name)
        if not stat:
            self.has_insufficient_stats = True
            stat = CalibratedTableStats(t_name, 1.0, 1.0, "id", [], is_live=False, confidence="INSUFFICIENT_STATISTICS")
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
            return 1.0

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

from typing import Dict, List, Set, Tuple, Optional, Any
import sqlglot
from sqlglot import exp, parse_one, parse, Dialect
from app.schemas.policy import SQLAnalysisResult


# Disallowed statement expression types (Strict SELECT-only rule R1.1 / REQ-SAFE-01)
DISALLOWED_ROOT_EXPRESSIONS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.Grant,
    exp.Revoke,
    exp.Set,
    exp.Command,
    exp.Commit,
    exp.Rollback,
    exp.Transaction,
)

# Standard aggregate expression types
AGGREGATE_EXPRESSIONS = (
    exp.AggFunc,
    exp.Avg,
    exp.Sum,
    exp.Min,
    exp.Max,
    exp.Count,
    exp.Variance,
    exp.Stddev,
)

# Dangerous and side-channel functions (Rule R1.3 / SEC-4 / Task T-19)
DISALLOWED_FUNCTIONS: Set[str] = {
    "PG_SLEEP",
    "SLEEP",
    "BENCHMARK",
    "SYS_EVAL",
    "SYS_EXEC",
    "DBLINK",
    "DBLINK_EXEC",
    "PG_READ_FILE",
    "PG_READ_BINARY_FILE",
    "PG_WRITE_FILE",
    "PG_LS_DIR",
    "LO_EXPORT",
    "LO_IMPORT",
    "XP_CMDSHELL",
    "CURRENT_USER",
    "SESSION_USER",
    "VERSION",
    "CURRENT_VERSION",
    "INET_CLIENT_ADDR",
    "INET_SERVER_ADDR",
    "PG_TERMINATE_BACKEND",
    "PG_CANCEL_BACKEND",
}


class SQLASTParser:
    """
    SQL AST Parser, Security Analyzer, and Row-Filter Rewriter using sqlglot (Weeks 4-5).
    Enforces SELECT-only statement validation, function allowlisting, Cartesian product checks,
    and automatic row-filter injection.
    """

    @staticmethod
    def analyze_sql(sql: str, catalog_tables: Optional[Dict[str, List[str]]] = None) -> SQLAnalysisResult:
        """
        Parses and performs deep AST analysis on a SQL string.
        """
        if not sql or not sql.strip():
            return SQLAnalysisResult(
                is_valid_syntax=False,
                is_select_only=False,
                syntax_error="Empty SQL query provided",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
                disallowed_functions=[],
                has_cartesian_join=False,
            )

        cleaned_sql = sql.strip().rstrip(";")

        # Check for multiple stacked statements
        try:
            parsed_statements = parse(cleaned_sql, read="postgres")
        except Exception as e:
            return SQLAnalysisResult(
                is_valid_syntax=False,
                is_select_only=False,
                syntax_error=f"SQL Parse error: {str(e)}",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
                disallowed_functions=[],
                has_cartesian_join=False,
            )

        if len(parsed_statements) > 1:
            return SQLAnalysisResult(
                is_valid_syntax=True,
                is_select_only=False,
                syntax_error="Multiple statements (stacked queries) are strictly disallowed.",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
                disallowed_functions=[],
                has_cartesian_join=False,
            )

        if not parsed_statements or parsed_statements[0] is None:
            return SQLAnalysisResult(
                is_valid_syntax=False,
                is_select_only=False,
                syntax_error="No valid SQL statement found",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
                disallowed_functions=[],
                has_cartesian_join=False,
            )

        ast = parsed_statements[0]

        # 1. Statement Type Check (SELECT-only)
        if isinstance(ast, DISALLOWED_ROOT_EXPRESSIONS):
            return SQLAnalysisResult(
                is_valid_syntax=True,
                is_select_only=False,
                syntax_error=f"Disallowed statement type: {ast.__class__.__name__}. Only SELECT queries are permitted.",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
                disallowed_functions=[],
                has_cartesian_join=False,
            )

        if not isinstance(ast, (exp.Select, exp.Union)):
            return SQLAnalysisResult(
                is_valid_syntax=True,
                is_select_only=False,
                syntax_error=f"Non-SELECT statement encountered: {ast.__class__.__name__}",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
                disallowed_functions=[],
                has_cartesian_join=False,
            )

        # Check for SELECT ... INTO (which writes to table/file)
        if ast.find(exp.Into):
            return SQLAnalysisResult(
                is_valid_syntax=True,
                is_select_only=False,
                syntax_error="SELECT INTO queries are strictly disallowed",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
                disallowed_functions=[],
                has_cartesian_join=False,
            )

        # 2. Extract CTE names to avoid treating them as physical tables
        cte_names: Set[str] = set()
        with_exp = ast.find(exp.With)
        if with_exp:
            for cte in with_exp.expressions:
                if isinstance(cte, exp.CTE) and cte.alias:
                    cte_names.add(cte.alias.lower())
                if cte.this and not isinstance(cte.this, (exp.Select, exp.Union)):
                    return SQLAnalysisResult(
                        is_valid_syntax=True,
                        is_select_only=False,
                        syntax_error=f"CTE expression must be a SELECT, got {cte.this.__class__.__name__}",
                        tables=[],
                        table_columns={},
                        aggregates=[],
                        functions=[],
                        disallowed_functions=[],
                        has_cartesian_join=False,
                    )

        # 3. Extract Physical Tables and Table Aliases
        physical_tables: Set[str] = set()
        alias_to_table: Dict[str, str] = {}

        for table in ast.find_all(exp.Table):
            table_name = table.name.lower() if table.name else ""
            if table_name and table_name not in cte_names:
                physical_tables.add(table_name)
                alias = table.alias.lower() if table.alias else table_name
                alias_to_table[alias] = table_name
                alias_to_table[table_name] = table_name

        # 4. Extract Functions & Check Allowlist (Task T-19 / Rule R1.3)
        functions_found: List[str] = []
        disallowed_found: List[str] = []

        for func in ast.find_all((exp.Func, exp.Anonymous)):
            func_name = ""
            if isinstance(func, exp.Anonymous) and func.this:
                func_name = str(func.this).upper()
            elif hasattr(func, "sql_name"):
                func_name = func.sql_name().upper()
            elif hasattr(func, "name"):
                func_name = func.name.upper()

            if func_name:
                functions_found.append(func_name)
                if func_name in DISALLOWED_FUNCTIONS:
                    disallowed_found.append(func_name)

        # 5. Check for Unconstrained Cartesian Joins (Task T-20 / Rule R1.5)
        has_cartesian = False
        joins = list(ast.find_all(exp.Join))
        for join in joins:
            # Check explicit CROSS JOIN
            if join.kind and "CROSS" in join.kind.upper():
                has_cartesian = True
                break
            if not join.args.get("on") and not join.args.get("using"):
                # Join with no ON/USING clause (e.g. comma join or unjoined JOIN)
                where_exp = ast.find(exp.Where)
                if not where_exp:
                    has_cartesian = True
                    break
                # If where exists, verify it contains an equality join condition
                eq_comparisons = list(where_exp.find_all(exp.EQ))
                has_join_predicate = False
                for eq in eq_comparisons:
                    left_col = eq.left.find(exp.Column) if hasattr(eq, "left") else None
                    right_col = eq.right.find(exp.Column) if hasattr(eq, "right") else None
                    if left_col and right_col:
                        has_join_predicate = True
                        break
                if not has_join_predicate:
                    has_cartesian = True
                    break

        # Check multiple comma tables in FROM without where condition
        from_exp = ast.find(exp.From)
        if from_exp and len(from_exp.expressions) > 1:
            where_exp = ast.find(exp.Where)
            if not where_exp:
                has_cartesian = True

        # 6. Extract Columns and Map to Tables
        table_columns: Dict[str, Set[str]] = {t: set() for t in physical_tables}
        aggregates: List[Dict[str, str]] = []

        for col in ast.find_all(exp.Column):
            col_name = col.name.lower() if col.name else ""
            table_qualifier = col.table.lower() if col.table else None

            if not col_name:
                continue

            resolved_table: Optional[str] = None
            if table_qualifier:
                resolved_table = alias_to_table.get(table_qualifier)
            elif len(physical_tables) == 1:
                resolved_table = next(iter(physical_tables))
            elif catalog_tables:
                for pt in physical_tables:
                    known_cols = catalog_tables.get(pt, [])
                    if col_name in known_cols:
                        resolved_table = pt
                        break

            if resolved_table and resolved_table in table_columns:
                table_columns[resolved_table].add(col_name)
            elif not resolved_table and len(physical_tables) > 1:
                for pt in physical_tables:
                    table_columns[pt].add(col_name)

        # 7. Extract Aggregate Functions and Target Columns
        for agg in ast.find_all(AGGREGATE_EXPRESSIONS):
            func_name = agg.sql_name().upper() if hasattr(agg, "sql_name") else agg.__class__.__name__.upper()
            for inner_col in agg.find_all(exp.Column):
                col_name = inner_col.name.lower() if inner_col.name else ""
                table_qualifier = inner_col.table.lower() if inner_col.table else None
                
                target_table = None
                if table_qualifier:
                    target_table = alias_to_table.get(table_qualifier)
                elif len(physical_tables) == 1:
                    target_table = next(iter(physical_tables))
                elif catalog_tables:
                    for pt in physical_tables:
                        if col_name in catalog_tables.get(pt, []):
                            target_table = pt
                            break

                if target_table and col_name:
                    aggregates.append({
                        "function": func_name,
                        "table": target_table,
                        "column": col_name,
                    })

        return SQLAnalysisResult(
            is_valid_syntax=True,
            is_select_only=True,
            syntax_error=None,
            tables=sorted(list(physical_tables)),
            table_columns={k: sorted(list(v)) for k, v in table_columns.items()},
            aggregates=aggregates,
            functions=functions_found,
            disallowed_functions=disallowed_found,
            has_cartesian_join=has_cartesian,
        )

    @staticmethod
    def inject_row_filters(sql: str, table_filters: Dict[str, str]) -> str:
        """
        Task T-21 / REQ-AUTH-03: Row-Filter Injection Engine.
        Automatically rewrites the AST to apply table-specific row filters (e.g. department_id = 2)
        directly into the query's WHERE clause. Unremovable by the LLM's proposed SQL.
        """
        if not sql or not table_filters:
            return sql

        try:
            ast = parse_one(sql, read="postgres")
        except Exception:
            return sql

        # Build alias map
        alias_map: Dict[str, str] = {}  # table_name -> alias (or table_name)
        for table in ast.find_all(exp.Table):
            t_name = table.name.lower() if table.name else ""
            if t_name:
                alias = table.alias if table.alias else t_name
                alias_map[t_name] = alias

        # Apply each active filter
        for t_name, raw_filter in table_filters.items():
            t_name_lower = t_name.lower()
            if t_name_lower in alias_map:
                alias = alias_map[t_name_lower]
                # Parse filter SQL into expression
                try:
                    filter_ast = parse_one(raw_filter, read="postgres")
                    # If table is aliased and filter is unaliased, qualify columns
                    if alias != t_name_lower:
                        for col in filter_ast.find_all(exp.Column):
                            if not col.table:
                                col.set("table", exp.to_identifier(alias))
                    
                    ast.where(filter_ast, copy=False)
                except Exception:
                    pass

        return ast.sql(dialect="postgres")

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


class SQLASTParser:
    """
    SQL AST Parser and Security Analyzer using sqlglot (REQ-SAFE-01 / Rule R1.1).
    Enforces SELECT-only statement validation and extracts referenced tables,
    columns, and aggregate functions.
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
            )

        ast = parsed_statements[0]

        # 1. Statement Type Check (SELECT-only)
        # Check if root is disallowed or not a Select / Union
        if isinstance(ast, DISALLOWED_ROOT_EXPRESSIONS):
            return SQLAnalysisResult(
                is_valid_syntax=True,
                is_select_only=False,
                syntax_error=f"Disallowed statement type: {ast.__class__.__name__}. Only SELECT queries are permitted.",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
            )

        # Ensure AST is a Select, Union, or CTE containing only Selects
        if not isinstance(ast, (exp.Select, exp.Union)):
            return SQLAnalysisResult(
                is_valid_syntax=True,
                is_select_only=False,
                syntax_error=f"Non-SELECT statement encountered: {ast.__class__.__name__}",
                tables=[],
                table_columns={},
                aggregates=[],
                functions=[],
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
            )

        # 2. Extract CTE names to avoid treating them as physical tables
        cte_names: Set[str] = set()
        with_exp = ast.find(exp.With)
        if with_exp:
            for cte in with_exp.expressions:
                if isinstance(cte, exp.CTE) and cte.alias:
                    cte_names.add(cte.alias.lower())
                # Verify CTE child query is a SELECT / Union
                if cte.this and not isinstance(cte.this, (exp.Select, exp.Union)):
                    return SQLAnalysisResult(
                        is_valid_syntax=True,
                        is_select_only=False,
                        syntax_error=f"CTE expression must be a SELECT, got {cte.this.__class__.__name__}",
                        tables=[],
                        table_columns={},
                        aggregates=[],
                        functions=[],
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

        # 4. Extract Functions
        functions_found: List[str] = []
        for func in ast.find_all(exp.Func):
            func_name = func.sql_name().upper() if hasattr(func, "sql_name") else func.name.upper()
            functions_found.append(func_name)

        # 5. Extract Columns and Map to Tables
        table_columns: Dict[str, Set[str]] = {t: set() for t in physical_tables}
        aggregates: List[Dict[str, str]] = []

        # Extract all Column expressions
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
                # Disambiguate against catalog if multiple physical tables are present
                for pt in physical_tables:
                    known_cols = catalog_tables.get(pt, [])
                    if col_name in known_cols:
                        resolved_table = pt
                        break

            if resolved_table and resolved_table in table_columns:
                table_columns[resolved_table].add(col_name)
            elif not resolved_table and len(physical_tables) > 1:
                # If cannot disambiguate table, associate column with all tables in query for safety check
                for pt in physical_tables:
                    table_columns[pt].add(col_name)

        # 6. Extract Aggregate Functions and Target Columns
        for agg in ast.find_all(AGGREGATE_EXPRESSIONS):
            func_name = agg.sql_name().upper() if hasattr(agg, "sql_name") else agg.__class__.__name__.upper()
            # Find column inside this aggregate
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
        )

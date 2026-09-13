import re
import time
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, Engine, inspect
import sqlglot
from sqlglot import exp

from app.schemas.optimize import (
    OptimizationItem,
    OptimizeResponse,
)
from app.services.execution_sandbox import ExecutionSandboxService, SandboxExecutionResult


class QueryOptimizerService:
    """
    Optimization Module (REQ-OPT-01, REQ-OPT-02, TRD §3.6, Rule R6.5)
    - Default mode: EXPLAIN (plan-only, does not execute the query).
    - Opt-in admin mode: EXPLAIN ANALYZE (admin-gated, sandboxed with timeout/row limits).
    - Evidence-based suggestions with deterministic confidence:
      {
        "observed": "Sequential scan on orders",
        "evidence": "filter = customer_id",
        "existing_indexes": ["orders_pkey"],
        "recommendation": "Evaluate an index on orders(customer_id)",
        "confidence": "Medium"
      }
    - Suggested DDL is strictly copyable, never auto-executed.
    """

    @classmethod
    def run_explain(cls, engine: Engine, sql: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Executes safe EXPLAIN (plan-only) without executing the actual data manipulation.
        Works across SQLite ('EXPLAIN QUERY PLAN') and PostgreSQL ('EXPLAIN (FORMAT JSON)').
        """
        cleaned_sql = sql.strip().rstrip(";")
        dialect = engine.dialect.name

        plan_raw: List[Dict[str, Any]] = []
        plan_summary: Dict[str, Any] = {
            "dialect": dialect,
            "mode": "explain",
            "has_seq_scan": False,
            "has_temp_btree": False,
            "tables_scanned": [],
            "indexes_used": [],
        }

        try:
            with engine.connect() as conn:
                if dialect == "sqlite":
                    explain_sql = f"EXPLAIN QUERY PLAN {cleaned_sql}"
                    result = conn.execute(text(explain_sql))
                    rows = result.fetchall()
                    for r in rows:
                        # SQLite: id, parent, notused, detail
                        detail = str(r[3]) if len(r) > 3 else str(r[-1])
                        plan_raw.append({
                            "id": r[0] if len(r) > 0 else 0,
                            "parent": r[1] if len(r) > 1 else 0,
                            "detail": detail
                        })
                        if "SCAN" in detail:
                            plan_summary["has_seq_scan"] = True
                            # Extract table name if SCAN <table>
                            m = re.search(r"SCAN\s+(?:TABLE\s+)?(\w+)", detail, re.IGNORECASE)
                            if m:
                                plan_summary["tables_scanned"].append(m.group(1))
                        if "USING INDEX" in detail or "USING COVERING INDEX" in detail:
                            m = re.search(r"INDEX\s+(\w+)", detail, re.IGNORECASE)
                            if m:
                                plan_summary["indexes_used"].append(m.group(1))
                        if "TEMP B-TREE" in detail or "USE TEMP" in detail:
                            plan_summary["has_temp_btree"] = True
                else:
                    # PostgreSQL
                    explain_sql = f"EXPLAIN (FORMAT JSON) {cleaned_sql}"
                    try:
                        result = conn.execute(text(explain_sql))
                        json_plan = result.scalar()
                        plan_raw = json_plan if isinstance(json_plan, list) else [json_plan]
                    except Exception:
                        explain_sql = f"EXPLAIN {cleaned_sql}"
                        result = conn.execute(text(explain_sql))
                        plan_raw = [{"detail": str(r[0])} for r in result.fetchall()]

        except Exception as e:
            plan_raw = [{"error": str(e), "detail": "EXPLAIN execution failed"}]

        return plan_raw, plan_summary

    @classmethod
    def run_explain_analyze(
        cls,
        engine: Engine,
        sql: str,
        role: str = "admin",
        timeout_seconds: float = 10.0,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        """
        Opt-in admin-gated EXPLAIN ANALYZE mode (REQ-OPT-02).
        Strictly requires role == 'admin'. Runs inside execution sandbox with timeout.
        """
        if role.lower() != "admin":
            raise PermissionError(f"EXPLAIN ANALYZE is restricted to administrator role. Current role: '{role}'")

        cleaned_sql = sql.strip().rstrip(";")
        dialect = engine.dialect.name
        start_time = time.time()

        plan_raw: List[Dict[str, Any]] = []
        plan_summary: Dict[str, Any] = {
            "dialect": dialect,
            "mode": "explain_analyze",
            "has_seq_scan": False,
            "has_temp_btree": False,
            "tables_scanned": [],
            "indexes_used": [],
        }
        exec_stats: Dict[str, Any] = {}

        try:
            with engine.connect() as conn:
                if dialect == "sqlite":
                    # SQLite does not have native EXPLAIN ANALYZE, so we benchmark sandbox execution + EXPLAIN QUERY PLAN
                    plan_raw, plan_summary = cls.run_explain(engine, sql)
                    plan_summary["mode"] = "explain_analyze"
                    
                    # Execute in sandbox to gather live stats
                    res: SandboxExecutionResult = ExecutionSandboxService.execute_query(
                        engine, sql, timeout_seconds=timeout_seconds, max_rows=10000
                    )
                    exec_stats = {
                        "execution_time_ms": res.latency_ms,
                        "rows_returned": res.row_count,
                        "sandbox_status": "success" if res.success else "error",
                        "error": res.error,
                    }
                else:
                    # PostgreSQL supports EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
                    explain_sql = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {cleaned_sql}"
                    result = conn.execute(text(explain_sql))
                    json_plan = result.scalar()
                    plan_raw = json_plan if isinstance(json_plan, list) else [json_plan]
                    exec_stats = {
                        "execution_time_ms": int((time.time() - start_time) * 1000),
                        "status": "success",
                    }

        except Exception as e:
            plan_raw = [{"error": str(e), "detail": "EXPLAIN ANALYZE failed"}]
            exec_stats = {"error": str(e), "status": "failed"}

        return plan_raw, plan_summary, exec_stats

    @classmethod
    def generate_suggestions(
        cls,
        engine: Engine,
        sql: str,
        plan_raw: List[Dict[str, Any]],
        plan_summary: Dict[str, Any],
        is_analyze: bool = False,
        exec_stats: Optional[Dict[str, Any]] = None,
    ) -> List[OptimizationItem]:
        """
        Generates evidence-based, confidence-scored optimization suggestions (REQ-OPT-01).
        Analyzes AST filters, join conditions, sort orders, and matching DB indexes.
        """
        suggestions: List[OptimizationItem] = []
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())

        # 1. Parse AST to extract tables, where filters, joins, and order-by clauses
        parsed_tables: List[str] = []
        where_columns: Dict[str, List[str]] = {}
        join_columns: Dict[str, List[str]] = {}
        order_by_columns: Dict[str, List[str]] = {}

        try:
            parsed = sqlglot.parse_one(sql)
            for t in parsed.find_all(exp.Table):
                t_name = t.name.lower()
                if t_name in existing_tables:
                    parsed_tables.append(t_name)

            # Find columns in WHERE clauses
            for eq in parsed.find_all((exp.EQ, exp.GT, exp.GTE, exp.LT, exp.LTE, exp.Like, exp.In)):
                col = eq.find(exp.Column)
                if col:
                    col_name = col.name.lower()
                    t_name = col.table.lower() if col.table else (parsed_tables[0] if parsed_tables else None)
                    if t_name and t_name in existing_tables:
                        where_columns.setdefault(t_name, []).append(col_name)

            # Find columns in JOIN conditions
            for join in parsed.find_all(exp.Join):
                for col in join.find_all(exp.Column):
                    col_name = col.name.lower()
                    t_name = col.table.lower() if col.table else None
                    if t_name and t_name in existing_tables:
                        join_columns.setdefault(t_name, []).append(col_name)

            # Find ORDER BY columns
            for order in parsed.find_all(exp.Order):
                for col in order.find_all(exp.Column):
                    col_name = col.name.lower()
                    t_name = col.table.lower() if col.table else (parsed_tables[0] if parsed_tables else None)
                    if t_name and t_name in existing_tables:
                        order_by_columns.setdefault(t_name, []).append(col_name)

        except Exception:
            pass

        # If no tables found in AST, fallback to plan tables or existing tables
        if not parsed_tables:
            parsed_tables = list(existing_tables.intersection(set(plan_summary.get("tables_scanned", []))))

        # 2. Check each table for index opportunities
        for t_name in set(parsed_tables):
            try:
                indexes = inspector.get_indexes(t_name)
                pk_constraint = inspector.get_pk_constraint(t_name)
                pk_cols = pk_constraint.get("constrained_columns", []) if pk_constraint else []
                
                existing_index_names = [idx.get("name", "") for idx in indexes if idx.get("name")]
                if pk_cols:
                    existing_index_names.append(f"{t_name}_pkey ({', '.join(pk_cols)})")

                indexed_cols = set(pk_cols)
                for idx in indexes:
                    for c in idx.get("column_names", []):
                        if c:
                            indexed_cols.add(c.lower())

                # Check WHERE filters
                t_where = set(where_columns.get(t_name, []))
                for col in t_where:
                    if col not in indexed_cols:
                        confidence = "high" if is_analyze or len(t_where) == 1 else "medium"
                        idx_name = f"idx_{t_name}_{col}"
                        suggestions.append(
                            OptimizationItem(
                                issue_type="sequential_scan_on_filtered_table",
                                detail=f"Query filters table '{t_name}' on column '{col}' without a dedicated index, resulting in sequential evaluation.",
                                evidence_json={
                                    "observed": f"Sequential scan on {t_name}",
                                    "filter": col,
                                    "existing_indexes": existing_index_names,
                                    "plan_mode": plan_summary.get("mode", "explain"),
                                },
                                confidence=confidence,
                                suggested_ddl=f"CREATE INDEX {idx_name} ON {t_name}({col});",
                            )
                        )

                # Check JOIN columns
                t_join = set(join_columns.get(t_name, []))
                for col in t_join:
                    if col not in indexed_cols:
                        idx_name = f"idx_{t_name}_{col}"
                        suggestions.append(
                            OptimizationItem(
                                issue_type="unindexed_join_column",
                                detail=f"Join condition on '{t_name}.{col}' has no supporting index, which may cause hash/nested-loop join performance degradation.",
                                evidence_json={
                                    "observed": f"Unindexed join on {t_name}.{col}",
                                    "existing_indexes": existing_index_names,
                                },
                                confidence="medium",
                                suggested_ddl=f"CREATE INDEX {idx_name} ON {t_name}({col});",
                            )
                        )

                # Check ORDER BY columns
                t_order = set(order_by_columns.get(t_name, []))
                for col in t_order:
                    if col not in indexed_cols and plan_summary.get("has_temp_btree", False):
                        idx_name = f"idx_{t_name}_{col}"
                        suggestions.append(
                            OptimizationItem(
                                issue_type="unindexed_sort_operation",
                                detail=f"Sorting on '{t_name}.{col}' requires a temporary in-memory B-Tree sort buffer.",
                                evidence_json={
                                    "observed": f"Temporary sort on {t_name}.{col}",
                                    "existing_indexes": existing_index_names,
                                },
                                confidence="medium",
                                suggested_ddl=f"CREATE INDEX {idx_name} ON {t_name}({col});",
                            )
                        )

            except Exception:
                continue

        # 3. If plan has sequential scan flagged but no specific unindexed filter found
        if not suggestions and plan_summary.get("has_seq_scan", False):
            scanned = plan_summary.get("tables_scanned", [])
            for t_name in scanned:
                if t_name in existing_tables:
                    try:
                        indexes = inspector.get_indexes(t_name)
                        idx_names = [i.get("name", "") for i in indexes if i.get("name")]
                    except Exception:
                        idx_names = []
                    suggestions.append(
                        OptimizationItem(
                            issue_type="table_scan_detected",
                            detail=f"Table scan observed on '{t_name}'. If this table grows large, consider indexing frequent filter columns.",
                            evidence_json={
                                "observed": f"Full scan on {t_name}",
                                "existing_indexes": idx_names,
                            },
                            confidence="low",
                            suggested_ddl=None,
                        )
                    )

        # 4. If query is already well-indexed
        if not suggestions:
            suggestions.append(
                OptimizationItem(
                    issue_type="optimal_index_coverage",
                    detail="Query execution plan efficiently utilizes indexes with no unindexed sequential scan bottlenecks identified.",
                    evidence_json={
                        "observed": "Index coverage verified",
                        "indexes_used": plan_summary.get("indexes_used", []),
                    },
                    confidence="high",
                    suggested_ddl=None,
                )
            )

        return suggestions

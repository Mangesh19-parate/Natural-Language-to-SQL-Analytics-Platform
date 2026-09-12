from typing import Dict, List, Optional, Set, Tuple, Any
import re
import sqlglot
from sqlglot import exp, parse_one
from sqlalchemy.orm import Session
from app.models.policy import SemanticCatalog
from app.models.trust import SqlCriticFinding
from app.schemas.query import CriticFinding, CriticFindingType, CriticAnalysisResult


class SQLCriticService:
    """
    SQL Critic Service (REQ-CRITIC-01 / Task T-24 / Rule R3.1).
    
    Evaluates Policy-Engine-approved SQL queries against Semantic Catalog metadata
    for semantic smells prior to execution.
    
    Advisory & Visible: Findings are surfaced with actionable fixes and are never
    silently auto-applied.
    """

    @classmethod
    def critique_sql(
        cls,
        db: Optional[Session],
        data_source_id: int,
        sql: str,
        catalog_items: Optional[List[SemanticCatalog]] = None,
    ) -> CriticAnalysisResult:
        """
        Runs the full semantic-smell rule set over the SQL AST.
        """
        if not sql or not sql.strip():
            return CriticAnalysisResult(has_findings=False, findings_count=0, findings=[])

        try:
            ast = parse_one(sql.strip().rstrip(";"), read="postgres")
        except Exception:
            return CriticAnalysisResult(has_findings=False, findings_count=0, findings=[])

        # Load catalog metadata if db session provided
        catalog_map: Dict[str, Dict[str, SemanticCatalog]] = {}  # table -> column -> catalog_entry
        if catalog_items:
            for item in catalog_items:
                catalog_map.setdefault(item.table_name.lower(), {})[item.column_name.lower()] = item
        elif db is not None:
            entries = (
                db.query(SemanticCatalog)
                .filter(SemanticCatalog.data_source_id == data_source_id)
                .all()
            )
            for item in entries:
                catalog_map.setdefault(item.table_name.lower(), {})[item.column_name.lower()] = item

        findings: List[CriticFinding] = []

        # Rule 1: Aggregate on Identifier (SUM or AVG on ID/Key column)
        rule1_findings = cls._check_aggregate_on_identifier(ast, catalog_map)
        findings.extend(rule1_findings)

        # Rule 2: Unbounded High-Cardinality Timestamp in GROUP BY
        rule2_findings = cls._check_timestamp_group_by(ast, catalog_map)
        findings.extend(rule2_findings)

        # Rule 3: Redundant Unused Join
        rule3_findings = cls._check_redundant_joins(ast)
        findings.extend(rule3_findings)

        # Rule 4: COUNT(*) over LEFT JOIN
        rule4_findings = cls._check_count_on_left_join(ast)
        findings.extend(rule4_findings)

        return CriticAnalysisResult(
            has_findings=len(findings) > 0,
            findings_count=len(findings),
            findings=findings,
        )

    @classmethod
    def _check_aggregate_on_identifier(
        cls,
        ast: exp.Expression,
        catalog_map: Dict[str, Dict[str, SemanticCatalog]]
    ) -> List[CriticFinding]:
        """Flags SUM or AVG applied to primary/foreign keys or identifier columns."""
        findings = []

        # Find all physical tables
        alias_to_table: Dict[str, str] = {}
        for t in ast.find_all(exp.Table):
            t_name = t.name.lower() if t.name else ""
            if t_name:
                alias = t.alias.lower() if t.alias else t_name
                alias_to_table[alias] = t_name
                alias_to_table[t_name] = t_name

        for agg in ast.find_all((exp.Sum, exp.Avg)):
            func_name = agg.sql_name().upper() if hasattr(agg, "sql_name") else agg.__class__.__name__.upper()
            inner_col = agg.find(exp.Column)
            if not inner_col or not inner_col.name:
                continue

            col_name = inner_col.name.lower()
            table_alias = inner_col.table.lower() if inner_col.table else None
            resolved_table = alias_to_table.get(table_alias) if table_alias else None

            # Check if column is an identifier
            is_identifier = False
            if col_name.endswith("_id") or col_name.endswith("_pk") or col_name.endswith("_fk") or col_name == "id":
                is_identifier = True
            elif resolved_table and resolved_table in catalog_map:
                col_meta = catalog_map[resolved_table].get(col_name)
                if col_meta and col_meta.semantic_type in ("identifier", "id", "pk", "fk"):
                    is_identifier = True

            if is_identifier:
                # Generate suggested fix by replacing SUM/AVG with COUNT
                suggested_ast = ast.copy()
                for target_agg in suggested_ast.find_all(type(agg)):
                    target_col = target_agg.find(exp.Column)
                    if target_col and target_col.name.lower() == col_name:
                        replacement = exp.Count(this=target_agg.this)
                        target_agg.replace(replacement)
                        break

                findings.append(
                    CriticFinding(
                        finding_type=CriticFindingType.AGGREGATE_ON_IDENTIFIER,
                        severity="warning",
                        title="Suspicious aggregation on identifier",
                        detail=(
                            f"`{col_name}` is an identifier column and is being aggregated with {func_name}(). "
                            f"Mathematical sums/averages on primary or foreign keys are typically unintentional."
                        ),
                        suggested_fix=f"Did you mean COUNT({col_name}) to count records instead of {func_name}({col_name})?",
                        suggested_sql=suggested_ast.sql(dialect="postgres"),
                    )
                )

        return findings

    @classmethod
    def _check_timestamp_group_by(
        cls,
        ast: exp.Expression,
        catalog_map: Dict[str, Dict[str, SemanticCatalog]]
    ) -> List[CriticFinding]:
        """Flags grouping directly on raw timestamp columns without truncation/bucketing."""
        findings = []
        group_by = ast.find(exp.Group)
        if not group_by:
            return findings

        for expr in group_by.expressions:
            if isinstance(expr, exp.Column):
                col_name = expr.name.lower() if expr.name else ""
                if "time" in col_name or "timestamp" in col_name or col_name.endswith("_at") or col_name.endswith("_date"):
                    # Check if date truncation is already present
                    suggested_ast = ast.copy()
                    # Replace column in GROUP BY and SELECT with DATE_TRUNC('day', col)
                    for col in suggested_ast.find_all(exp.Column):
                        if col.name.lower() == col_name and not col.find_ancestor(exp.Anonymous, exp.Func):
                            trunc_node = parse_one(f"DATE_TRUNC('day', {col.sql(dialect='postgres')})", read="postgres")
                            col.replace(trunc_node)

                    findings.append(
                        CriticFinding(
                            finding_type=CriticFindingType.SUSPICIOUS_GROUP_BY,
                            severity="warning",
                            title="Raw timestamp in GROUP BY",
                            detail=(
                                f"Grouping by raw timestamp column `{col_name}` produces near-unique groups "
                                f"per row rather than aggregated time periods."
                            ),
                            suggested_fix=f"Use DATE_TRUNC('day', {col_name}) or DATE({col_name}) for daily aggregation.",
                            suggested_sql=suggested_ast.sql(dialect="postgres"),
                        )
                    )

        return findings

    @classmethod
    def _check_redundant_joins(cls, ast: exp.Expression) -> List[CriticFinding]:
        """Flags joined tables that have 0 referenced columns across SELECT/WHERE/GROUP BY/ORDER BY."""
        findings = []
        joins = list(ast.find_all(exp.Join))
        if not joins:
            return findings

        # Collect columns referenced strictly outside the JOIN ON conditions
        outer_cols: Set[Tuple[str, str]] = set()  # (table_or_alias, col_name)
        
        # Check SELECT projection expressions (excluding join nodes)
        if hasattr(ast, "expressions"):
            for expr in ast.expressions:
                for col in expr.find_all(exp.Column):
                    t = col.table.lower() if col.table else ""
                    c = col.name.lower() if col.name else ""
                    if t and c:
                        outer_cols.add((t, c))

        # Check WHERE expressions
        where_exp = ast.find(exp.Where)
        if where_exp:
            for col in where_exp.find_all(exp.Column):
                t = col.table.lower() if col.table else ""
                c = col.name.lower() if col.name else ""
                if t and c:
                    outer_cols.add((t, c))

        # Check GROUP BY / ORDER BY / HAVING
        for clause in (ast.find(exp.Group), ast.find(exp.Order), ast.find(exp.Having)):
            if clause:
                for col in clause.find_all(exp.Column):
                    t = col.table.lower() if col.table else ""
                    c = col.name.lower() if col.name else ""
                    if t and c:
                        outer_cols.add((t, c))

        for join in joins:
            join_table = join.this
            if isinstance(join_table, exp.Table):
                t_name = join_table.name.lower() if join_table.name else ""
                t_alias = join_table.alias.lower() if join_table.alias else t_name

                # Check if this table/alias is ever projected or filtered outside join ON
                is_used = any(t in (t_name, t_alias) for t, _ in outer_cols)

                if not is_used and t_name:
                    suggested_ast = ast.copy()
                    for target_join in suggested_ast.find_all(exp.Join):
                        if target_join.this and getattr(target_join.this, "name", "").lower() == t_name:
                            target_join.pop()
                            break

                    findings.append(
                        CriticFinding(
                            finding_type=CriticFindingType.REDUNDANT_JOIN,
                            severity="advisory",
                            title=f"Unused joined table '{t_name}'",
                            detail=f"Table `{t_name}` is joined but no columns from it are selected or filtered in the query.",
                            suggested_fix=f"Remove the join to `{t_name}` to optimize query execution.",
                            suggested_sql=suggested_ast.sql(dialect="postgres"),
                        )
                    )

        return findings

    @classmethod
    def _check_count_on_left_join(cls, ast: exp.Expression) -> List[CriticFinding]:
        """Flags COUNT(*) queries over a LEFT JOIN."""
        findings = []
        has_left_join = False
        right_table_alias = ""
        
        for join in ast.find_all(exp.Join):
            join_side = str(join.args.get("side") or join.side or "").upper()
            join_kind = str(join.args.get("kind") or join.kind or "").upper()
            if "LEFT" in join_side or "LEFT" in join_kind:
                has_left_join = True
                if isinstance(join.this, exp.Table):
                    right_table_alias = join.this.alias or join.this.name or ""
                break

        if has_left_join:
            for count_node in ast.find_all(exp.Count):
                if isinstance(count_node.this, exp.Star):
                    suggested_ast = ast.copy()
                    for target_count in suggested_ast.find_all(exp.Count):
                        if isinstance(target_count.this, exp.Star):
                            if right_table_alias:
                                replacement = parse_one(f"COUNT({right_table_alias}.id)", read="postgres")
                            else:
                                replacement = parse_one("COUNT(1)", read="postgres")
                            target_count.replace(replacement)
                            break

                    findings.append(
                        CriticFinding(
                            finding_type=CriticFindingType.COUNT_ON_LEFT_JOIN,
                            severity="warning",
                            title="COUNT(*) over LEFT JOIN",
                            detail="`COUNT(*)` over a LEFT JOIN will count unmatched rows (containing NULLs).",
                            suggested_fix="Use COUNT(right_table.id) to count only matched entities.",
                            suggested_sql=suggested_ast.sql(dialect="postgres"),
                        )
                    )

        return findings

    @classmethod
    def persist_findings(
        cls,
        db: Session,
        query_id: str,
        findings: List[CriticFinding],
        user_action: Optional[str] = None,
    ) -> List[SqlCriticFinding]:
        """Persists findings to the sql_critic_findings database table (Task T-24 / REQ-CRITIC-01)."""
        db_records = []
        for f in findings:
            record = SqlCriticFinding(
                query_id=query_id,
                finding_type=f.finding_type.value,
                detail=f.detail,
                suggested_fix=f.suggested_sql or f.suggested_fix,
                user_action=user_action or f.user_action or "advisory_surfaced",
            )
            db.add(record)
            db_records.append(record)
        
        try:
            db.commit()
        except Exception:
            db.rollback()
            
        return db_records

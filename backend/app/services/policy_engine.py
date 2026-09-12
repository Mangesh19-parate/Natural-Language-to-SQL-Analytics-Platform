from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from app.models.policy import DataPolicy, SemanticCatalog
from app.schemas.policy import (
    EffectiveTablePolicy,
    EffectivePolicySummary,
    PolicyValidationResult,
    PolicyViolation,
    PolicyViolationType,
    SQLAnalysisResult,
)
from app.services.sql_parser import SQLASTParser


class PolicyLookupService:
    """
    Fail-Closed Policy Engine Lookup Service (REQ-AUTH-02 / Rule R1.2).
    
    Guarantees:
    - DENY BY DEFAULT: If no explicit data_policy row exists for (role_id, data_source_id, table_name),
      access to that table is 0 (completely inaccessible).
    - COLUMN-LEVEL GRANULARITY: Specific column grants/denials override table-level defaults.
    - AGGREGATE FUNCTION GUARD: Sensitive columns cannot be aggregated unless aggregate_allowed=True.
    - ROW FILTER INJECTION: Enforces data_policy.row_filter_sql if present.
    """

    @staticmethod
    def get_effective_policy(db: Session, role_id: int, data_source_id: int) -> EffectivePolicySummary:
        """
        Retrieves the complete effective policy map for a given role and data source.
        Only tables with explicit non-denied rows will be included.
        """
        policies = (
            db.query(DataPolicy)
            .filter(
                DataPolicy.role_id == role_id,
                DataPolicy.data_source_id == data_source_id
            )
            .all()
        )

        summary = EffectivePolicySummary(role_id=role_id, data_source_id=data_source_id, accessible_tables={})

        if not policies:
            # Strictly FAIL-CLOSED: empty accessible_tables map
            return summary

        # Group by table_name
        table_policy_rows: Dict[str, List[DataPolicy]] = {}
        for p in policies:
            table_policy_rows.setdefault(p.table_name.lower(), []).append(p)

        for table_name, rows in table_policy_rows.items():
            # Check if there is a table-level rule (column_name is NULL)
            table_level_row = next((r for r in rows if r.column_name is None), None)
            column_rows = [r for r in rows if r.column_name is not None]

            table_accessible = False
            effective_access_level = "denied"
            row_filter_sql = None
            allowed_cols: Set[str] = set()
            denied_cols: Set[str] = set()
            agg_allowed_cols: Set[str] = set()

            if table_level_row:
                if table_level_row.access_level in ("read", "read_aggregate_only"):
                    table_accessible = True
                    effective_access_level = table_level_row.access_level
                row_filter_sql = table_level_row.row_filter_sql
                if table_level_row.aggregate_allowed:
                    agg_allowed_cols.add("*")

            # Apply column-specific rules
            for c_row in column_rows:
                c_name = c_row.column_name.lower()
                if c_row.access_level == "denied":
                    denied_cols.add(c_name)
                    allowed_cols.discard(c_name)
                elif c_row.access_level in ("read", "read_aggregate_only"):
                    table_accessible = True  # If at least one column is readable, table is accessible for those columns
                    allowed_cols.add(c_name)
                    denied_cols.discard(c_name)

                if c_row.aggregate_allowed:
                    agg_allowed_cols.add(c_name)
                if c_row.row_filter_sql and not row_filter_sql:
                    row_filter_sql = c_row.row_filter_sql

            if table_accessible:
                summary.accessible_tables[table_name] = EffectiveTablePolicy(
                    table_name=table_name,
                    accessible=True,
                    access_level=effective_access_level,
                    allowed_columns=list(allowed_cols),
                    denied_columns=list(denied_cols),
                    aggregate_allowed_columns=list(agg_allowed_cols),
                    row_filter_sql=row_filter_sql,
                )

        return summary

    @staticmethod
    def is_table_accessible(db: Session, role_id: int, data_source_id: int, table_name: str) -> bool:
        """Deny-by-default check: is the given table accessible by this role? (Rule R1.2 / T-16)"""
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        return table_name.lower() in policy.accessible_tables and policy.accessible_tables[table_name.lower()].accessible

    @staticmethod
    def is_column_accessible(db: Session, role_id: int, data_source_id: int, table_name: str, column_name: str) -> bool:
        """Deny-by-default check: is the given column accessible by this role? (Rule R1.2 / T-17)"""
        t_name = table_name.lower()
        c_name = column_name.lower()
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        
        if t_name not in policy.accessible_tables:
            return False
        
        table_pol = policy.accessible_tables[t_name]
        
        # If column is explicitly denied
        if c_name in table_pol.denied_columns:
            return False
        
        # If explicit allowed columns are listed, must be in allowed_columns
        if table_pol.allowed_columns:
            return c_name in table_pol.allowed_columns
        
        # Otherwise, if table itself is readable and no column exclusions
        return table_pol.access_level in ("read", "read_aggregate_only")

    @staticmethod
    def is_aggregate_allowed(db: Session, role_id: int, data_source_id: int, table_name: str, column_name: str) -> bool:
        """Checks if aggregate functions (AVG, SUM, MIN, MAX) are permitted on a sensitive column (Rule R1.4 / T-18)."""
        t_name = table_name.lower()
        c_name = column_name.lower()
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        
        if t_name not in policy.accessible_tables:
            return False
        
        table_pol = policy.accessible_tables[t_name]
        
        # Check if table-level has aggregate_allowed="*" or column has explicit aggregate_allowed
        if "*" in table_pol.aggregate_allowed_columns or c_name in table_pol.aggregate_allowed_columns:
            return True
            
        # Check semantic catalog sensitivity: if LOW or NONE sensitivity, aggregation is allowed by default
        catalog_entry = (
            db.query(SemanticCatalog)
            .filter(
                SemanticCatalog.data_source_id == data_source_id,
                SemanticCatalog.table_name == t_name,
                SemanticCatalog.column_name == c_name,
            )
            .first()
        )
        if catalog_entry and catalog_entry.sensitivity in ("NONE", "LOW"):
            return True
            
        return False

    @staticmethod
    def get_row_filter(db: Session, role_id: int, data_source_id: int, table_name: str) -> Optional[str]:
        """Retrieves row-level filter SQL clause to be injected for this role (Rule R1.2 / SEC-3)."""
        t_name = table_name.lower()
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        if t_name not in policy.accessible_tables:
            return None
        return policy.accessible_tables[t_name].row_filter_sql


class PolicyEngine:
    """
    Core Policy Enforcement Engine (Weeks 4-5 / REQ-SAFE-01, REQ-SAFE-02, REQ-AUTH-03, REQ-SAFE-03, REQ-SAFE-04).
    Deterministic authorization gate:
    1. AST Statement-Type Validation (SELECT-only, blocks DDL/DML/multi-statement)
    2. Function / Operator Allowlist (Blocks dangerous sleep/file/link functions - T-19)
    3. Resource / Cost Pre-check (Blocks Cartesian joins / unconstrained products - T-20)
    4. Table Authorization (deny-by-default, fail-closed - T-16)
    5. Column Authorization (per-column access validation - T-17)
    6. Aggregate Function Guard (blocks AVG/SUM/etc. on sensitive columns - T-18)
    7. Row-Filter Injection (applies role-specific row filters unbypassably - T-21)
    """

    @classmethod
    def validate_sql(
        cls,
        db: Session,
        role_id: int,
        data_source_id: int,
        sql: str,
        catalog_tables: Optional[Dict[str, List[str]]] = None,
    ) -> PolicyValidationResult:
        """
        Runs comprehensive deterministic policy validation on a proposed SQL query.
        """
        violations: List[PolicyViolation] = []

        # If catalog_tables not provided, fetch from DB
        if catalog_tables is None:
            catalog_rows = (
                db.query(SemanticCatalog)
                .filter(SemanticCatalog.data_source_id == data_source_id)
                .all()
            )
            catalog_tables = {}
            for row in catalog_rows:
                catalog_tables.setdefault(row.table_name.lower(), []).append(row.column_name.lower())

        # Step 1: AST Parsing & Statement-Type Validation (T-15 / REQ-SAFE-01)
        analysis: SQLAnalysisResult = SQLASTParser.analyze_sql(sql, catalog_tables)

        if not analysis.is_valid_syntax:
            violations.append(
                PolicyViolation(
                    violation_type=PolicyViolationType.SYNTAX_ERROR,
                    message=f"SQL Syntax Error: {analysis.syntax_error}",
                )
            )
            return PolicyValidationResult(
                is_allowed=False,
                status="REJECTED",
                violations=violations,
                effective_tables=[],
            )

        if not analysis.is_select_only:
            violations.append(
                PolicyViolation(
                    violation_type=PolicyViolationType.STATEMENT_NOT_ALLOWED,
                    message=analysis.syntax_error or "Only SELECT queries are permitted (Rule R1.1).",
                )
            )
            return PolicyValidationResult(
                is_allowed=False,
                status="REJECTED",
                violations=violations,
                effective_tables=[],
            )

        # Step 2: Function Allowlist Check (T-19 / Rule R1.3 / SEC-4)
        if analysis.disallowed_functions:
            for d_func in analysis.disallowed_functions:
                violations.append(
                    PolicyViolation(
                        violation_type=PolicyViolationType.DISALLOWED_FUNCTION,
                        function_name=d_func,
                        message=f"Disallowed function '{d_func}' is blocked by security policy (Rule R1.3).",
                    )
                )

        # Step 3: Resource Limits & Cartesian Product Check (T-20 / Rule R1.5 / SEC-5)
        if analysis.has_cartesian_join:
            violations.append(
                PolicyViolation(
                    violation_type=PolicyViolationType.CARTESIAN_PRODUCT_BLOCKED,
                    message="Unconstrained Cartesian join detected. Queries must include explicit join conditions (Rule R1.5).",
                )
            )

        # Step 4: Schema / Table Authorization (T-16 / REQ-SAFE-02 — Deny by default)
        for table_name in analysis.tables:
            if not PolicyLookupService.is_table_accessible(db, role_id, data_source_id, table_name):
                violations.append(
                    PolicyViolation(
                        violation_type=PolicyViolationType.UNAUTHORIZED_TABLE,
                        table_name=table_name,
                        message=f"Access to table '{table_name}' is denied by default (no explicit permission).",
                    )
                )

        # If any blocking violations exist up to this point, stop with detailed report
        if violations:
            return PolicyValidationResult(
                is_allowed=False,
                status="REJECTED",
                violations=violations,
                effective_tables=analysis.tables,
            )

        # Step 5: Column Authorization (T-17 / REQ-SAFE-02)
        for table_name, columns in analysis.table_columns.items():
            for col_name in columns:
                if not PolicyLookupService.is_column_accessible(db, role_id, data_source_id, table_name, col_name):
                    violations.append(
                        PolicyViolation(
                            violation_type=PolicyViolationType.UNAUTHORIZED_COLUMN,
                            table_name=table_name,
                            column_name=col_name,
                            message=f"Access to column '{table_name}.{col_name}' is denied for your role.",
                        )
                    )

        # Step 6: Aggregate Function Guard (T-18 / REQ-AUTH-03 / Rule R1.4)
        for agg in analysis.aggregates:
            func = agg["function"]
            t_name = agg["table"]
            c_name = agg["column"]

            if not PolicyLookupService.is_aggregate_allowed(db, role_id, data_source_id, t_name, c_name):
                violations.append(
                    PolicyViolation(
                        violation_type=PolicyViolationType.UNAUTHORIZED_AGGREGATE,
                        table_name=t_name,
                        column_name=c_name,
                        function_name=func,
                        message=(
                            f"Aggregate function {func}() on sensitive column '{t_name}.{c_name}' "
                            f"is not permitted for your role (Rule R1.4)."
                        ),
                    )
                )

        # Step 7: Collect and Inject Applicable Row Filters (T-21 / Rule R1.2 / SEC-3)
        applied_row_filters: Dict[str, str] = {}
        for t_name in analysis.tables:
            rf = PolicyLookupService.get_row_filter(db, role_id, data_source_id, t_name)
            if rf:
                applied_row_filters[t_name] = rf

        is_allowed = len(violations) == 0
        injected_sql = None
        if is_allowed:
            if applied_row_filters:
                injected_sql = SQLASTParser.inject_row_filters(sql, applied_row_filters)
            else:
                injected_sql = sql.strip().rstrip(";")

        return PolicyValidationResult(
            is_allowed=is_allowed,
            status="APPROVED" if is_allowed else "REJECTED",
            violations=violations,
            effective_tables=analysis.tables,
            applied_row_filters=applied_row_filters,
            injected_sql=injected_sql,
        )

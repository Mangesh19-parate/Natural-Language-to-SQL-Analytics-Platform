from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from app.models.policy import DataPolicy
from app.schemas.policy import EffectiveTablePolicy, EffectivePolicySummary


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
            table_policy_rows.setdefault(p.table_name, []).append(p)

        for table_name, rows in table_policy_rows.items():
            # Check if there is a table-level rule (column_name is NULL)
            table_level_row = next((r for r in rows if r.column_name is None), None)
            column_rows = [r for r in rows if r.column_name is not None]

            # If no table-level row exists and no column rows exist, or table-level is 'denied' with no column reads
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
                if c_row.access_level == "denied":
                    denied_cols.add(c_row.column_name)
                    allowed_cols.discard(c_row.column_name)
                elif c_row.access_level in ("read", "read_aggregate_only"):
                    table_accessible = True  # If at least one column is readable, table is accessible for those columns
                    allowed_cols.add(c_row.column_name)
                    denied_cols.discard(c_row.column_name)

                if c_row.aggregate_allowed:
                    agg_allowed_cols.add(c_row.column_name)
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
        """Deny-by-default check: is the given table accessible by this role?"""
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        return table_name in policy.accessible_tables and policy.accessible_tables[table_name].accessible

    @staticmethod
    def is_column_accessible(db: Session, role_id: int, data_source_id: int, table_name: str, column_name: str) -> bool:
        """Deny-by-default check: is the given column accessible by this role?"""
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        if table_name not in policy.accessible_tables:
            return False
        
        table_pol = policy.accessible_tables[table_name]
        # If column is explicitly denied
        if column_name in table_pol.denied_columns:
            return False
        
        # If explicit allowed columns are listed, must be in allowed_columns
        if table_pol.allowed_columns:
            return column_name in table_pol.allowed_columns
        
        # Otherwise, if table itself is readable and no column exclusions
        return table_pol.access_level in ("read", "read_aggregate_only")

    @staticmethod
    def is_aggregate_allowed(db: Session, role_id: int, data_source_id: int, table_name: str, column_name: str) -> bool:
        """Checks if aggregate functions (AVG, SUM, MIN, MAX) are permitted on a sensitive column (Rule R1.4)."""
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        if table_name not in policy.accessible_tables:
            return False
        
        table_pol = policy.accessible_tables[table_name]
        return "*" in table_pol.aggregate_allowed_columns or column_name in table_pol.aggregate_allowed_columns

    @staticmethod
    def get_row_filter(db: Session, role_id: int, data_source_id: int, table_name: str) -> Optional[str]:
        """Retrieves row-level filter SQL clause to be injected for this role (Rule R1.2 / SEC-3)."""
        policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        if table_name not in policy.accessible_tables:
            return None
        return policy.accessible_tables[table_name].row_filter_sql

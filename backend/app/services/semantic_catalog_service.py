from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import Engine
from app.models.policy import DataSource, SemanticCatalog
from app.models.auth import Role
from app.services.policy_engine import PolicyLookupService
from app.services.schema_introspector import SchemaIntrospectorService
from app.schemas.catalog import ColumnCatalogItem, TableCatalogItem, SemanticCatalogResponse


class SemanticCatalogService:
    """
    Semantic Catalog Retrieval Service (REQ-CATALOG-01 / Task T-08).
    Retrieves typed, sensitivity-tagged schema representation strictly policy-filtered per role.
    """

    @staticmethod
    def get_catalog_for_role(
        db: Session,
        data_source_id: int,
        role_id: Optional[int],
        business_engine: Optional[Engine] = None
    ) -> SemanticCatalogResponse:
        ds = db.query(DataSource).filter(DataSource.data_source_id == data_source_id).first()
        if not ds:
            raise ValueError(f"DataSource {data_source_id} not found")

        role_name = None
        if role_id:
            role_obj = db.query(Role).filter(Role.role_id == role_id).first()
            if role_obj:
                role_name = role_obj.role_name

        response = SemanticCatalogResponse(
            data_source_id=ds.data_source_id,
            data_source_name=ds.name,
            role_id=role_id,
            role_name=role_name,
            tables=[]
        )

        # 1. Enforce Fail-Closed Security: If no role_id provided or unconfigured, return empty tables
        if not role_id:
            return response

        effective_policy = PolicyLookupService.get_effective_policy(db, role_id, data_source_id)
        if not effective_policy.accessible_tables:
            return response

        # 2. Get introspected FKs and PKs if engine provided
        fks_by_table: Dict[str, List[Dict[str, str]]] = {}
        pks_by_table: Dict[str, List[str]] = {}
        if business_engine:
            try:
                introspected = SchemaIntrospectorService.introspect_database(business_engine)
                for t in introspected:
                    pks_by_table[t.table_name] = t.primary_keys
                    fks_by_table[t.table_name] = [
                        {
                            "constrained_columns": fk.constrained_columns,
                            "referred_table": fk.referred_table,
                            "referred_columns": fk.referred_columns
                        }
                        for fk in t.foreign_keys
                    ]
            except Exception:
                pass

        # 3. Fetch all catalog entries for this data source
        all_catalog_entries = (
            db.query(SemanticCatalog)
            .filter(SemanticCatalog.data_source_id == data_source_id)
            .all()
        )

        # Group by table
        entries_by_table: Dict[str, List[SemanticCatalog]] = {}
        for entry in all_catalog_entries:
            entries_by_table.setdefault(entry.table_name, []).append(entry)

        # 4. Filter strictly by accessible_tables
        for table_name, table_policy in effective_policy.accessible_tables.items():
            if not table_policy.accessible:
                continue

            catalog_cols = entries_by_table.get(table_name, [])
            columns: List[ColumnCatalogItem] = []

            for col in catalog_cols:
                # Column check: must not be denied
                if col.column_name in table_policy.denied_columns:
                    continue
                # If explicit allowed columns list is defined, must be in allowed_columns
                if table_policy.allowed_columns and col.column_name not in table_policy.allowed_columns:
                    continue

                columns.append(
                    ColumnCatalogItem(
                        column_name=col.column_name,
                        data_type=col.data_type,
                        semantic_type=col.semantic_type,
                        sensitivity=col.sensitivity or "NONE",
                        default_aggregation=col.default_aggregation,
                        sanitized_examples=col.sanitized_examples,
                        description=col.description
                    )
                )

            # Filter foreign keys: only include FKs where both source and referred table are accessible
            raw_fks = fks_by_table.get(table_name, [])
            filtered_fks = [
                fk for fk in raw_fks
                if fk["referred_table"] in effective_policy.accessible_tables
            ]

            response.tables.append(
                TableCatalogItem(
                    table_name=table_name,
                    description=f"Business entity {table_name}",
                    columns=columns,
                    primary_keys=pks_by_table.get(table_name, []),
                    foreign_keys=filtered_fks
                )
            )

        return response

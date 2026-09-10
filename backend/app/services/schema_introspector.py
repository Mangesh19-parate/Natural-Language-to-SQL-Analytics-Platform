from typing import List, Dict, Any, Optional
from sqlalchemy import inspect, Engine
from pydantic import BaseModel


class IntrospectedColumn(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    primary_key: bool = False
    default: Optional[str] = None


class IntrospectedForeignKey(BaseModel):
    constrained_columns: List[str]
    referred_table: str
    referred_columns: List[str]


class IntrospectedTable(BaseModel):
    table_name: str
    columns: List[IntrospectedColumn] = []
    primary_keys: List[str] = []
    foreign_keys: List[IntrospectedForeignKey] = []


class SchemaIntrospectorService:
    """
    Schema Introspection Service (REQ-NLSQL-01 / Task T-06).
    Introspects tables, columns, data types, primary keys, and foreign keys from any connected database.
    """

    @staticmethod
    def introspect_database(engine: Engine, schema: Optional[str] = None) -> List[IntrospectedTable]:
        inspector = inspect(engine)
        table_names = inspector.get_table_names(schema=schema)
        
        introspected_tables: List[IntrospectedTable] = []

        for t_name in table_names:
            columns_raw = inspector.get_columns(t_name, schema=schema)
            pk_constraint = inspector.get_pk_constraint(t_name, schema=schema)
            primary_keys = pk_constraint.get("constrained_columns", []) if pk_constraint else []
            fks_raw = inspector.get_foreign_keys(t_name, schema=schema)

            columns: List[IntrospectedColumn] = []
            for col in columns_raw:
                c_name = col["name"]
                c_type = str(col["type"])
                is_pk = c_name in primary_keys or col.get("primary_key", False)
                columns.append(
                    IntrospectedColumn(
                        name=c_name,
                        data_type=c_type,
                        nullable=col.get("nullable", True),
                        primary_key=bool(is_pk),
                        default=str(col.get("default")) if col.get("default") is not None else None,
                    )
                )

            foreign_keys: List[IntrospectedForeignKey] = []
            for fk in fks_raw:
                foreign_keys.append(
                    IntrospectedForeignKey(
                        constrained_columns=fk.get("constrained_columns", []),
                        referred_table=fk.get("referred_table", ""),
                        referred_columns=fk.get("referred_columns", []),
                    )
                )

            introspected_tables.append(
                IntrospectedTable(
                    table_name=t_name,
                    columns=columns,
                    primary_keys=primary_keys,
                    foreign_keys=foreign_keys,
                )
            )

        return introspected_tables

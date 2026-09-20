from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ColumnCatalogItem(BaseModel):
    column_name: str
    data_type: Optional[str] = None
    semantic_type: Optional[str] = None  # 'monetary' | 'identifier' | 'categorical' | 'temporal' | 'metric' | 'text'
    sensitivity: str = "NONE"  # 'NONE' | 'LOW' | 'MEDIUM' | 'HIGH'
    default_aggregation: Optional[str] = None  # 'SUM' | 'AVG' | 'COUNT'
    sanitized_examples: Optional[List[str]] = None
    description: Optional[str] = None


class TableCatalogItem(BaseModel):
    table_name: str
    description: Optional[str] = None
    columns: List[ColumnCatalogItem] = []
    primary_keys: List[str] = []
    foreign_keys: List[Dict[str, Any]] = []  # e.g. [{"constrained_columns": ["customer_id"], "referred_table": "customers", "referred_columns": ["customer_id"]}]


class SemanticCatalogResponse(BaseModel):
    data_source_id: int
    data_source_name: str
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    tables: List[TableCatalogItem] = []


class DataSourceItemResponse(BaseModel):
    data_source_id: int
    name: str
    db_type: str
    is_active: bool
    description: Optional[str] = None


from typing import Optional, List, Dict
from pydantic import BaseModel


class DataPolicyCreate(BaseModel):
    role_id: int
    data_source_id: int
    table_name: str
    column_name: Optional[str] = None
    access_level: str = "read"  # 'denied' | 'read' | 'read_aggregate_only'
    aggregate_allowed: bool = False
    row_filter_sql: Optional[str] = None


class EffectiveTablePolicy(BaseModel):
    table_name: str
    accessible: bool = False
    access_level: str = "denied"
    allowed_columns: List[str] = []
    denied_columns: List[str] = []
    aggregate_allowed_columns: List[str] = []
    row_filter_sql: Optional[str] = None


class EffectivePolicySummary(BaseModel):
    role_id: int
    data_source_id: int
    accessible_tables: Dict[str, EffectiveTablePolicy] = {}

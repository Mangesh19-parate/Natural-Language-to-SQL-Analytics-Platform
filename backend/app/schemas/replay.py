from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.query import SQLExecuteResponse


class SchemaDriftReport(BaseModel):
    has_drift: bool
    drift_warning: Optional[str] = None
    historical_snapshot_id: Optional[str] = None
    historical_captured_at: Optional[datetime] = None
    added_tables: List[str] = Field(default_factory=list)
    removed_tables: List[str] = Field(default_factory=list)
    modified_columns: List[Dict[str, Any]] = Field(default_factory=list)
    sensitivity_changes: List[Dict[str, Any]] = Field(default_factory=list)
    summary: str

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class ProvenancePackage(BaseModel):
    query_id: str
    nl_question: str
    final_sql: Optional[str] = None
    dialect: str = "postgresql"
    schema_snapshot_id: Optional[str] = None
    prompt_version: Optional[str] = "v1.4"
    model_name: Optional[str] = "gpt-4o-mini"
    model_params: Optional[Dict[str, Any]] = None
    result_hash: Optional[str] = None
    execution_ms: Optional[int] = None
    row_count: Optional[int] = None
    reliability_breakdown: Optional[Dict[str, Any]] = None
    critic_summary: List[Dict[str, Any]] = Field(default_factory=list)
    validation_summary: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    drift_report: Optional[SchemaDriftReport] = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class QueryReplayResponse(BaseModel):
    query_id: str
    provenance: ProvenancePackage
    replayed_execution: SQLExecuteResponse
    replayed_result_hash: Optional[str] = None
    is_reproducible: bool
    reproducibility_message: str

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

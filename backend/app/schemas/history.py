from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class QueryHistorySummary(BaseModel):
    query_id: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    nl_question: str
    classification: Optional[str] = None
    status: str  # 'success' | 'auto_corrected' | 'failed' | 'rejected_policy' | 'rejected_unsupported'
    execution_ms: Optional[int] = None
    row_count: Optional[int] = None
    chart_type: Optional[str] = None
    final_sql: Optional[str] = None
    reliability_score: Optional[float] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class QueryHistoryDetail(BaseModel):
    query_id: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    nl_question: str
    classification: Optional[str] = None
    ambiguity_flag: bool = False
    clarification_asked: Optional[str] = None
    initial_sql: Optional[str] = None
    final_sql: Optional[str] = None
    dialect: Optional[str] = "postgresql"
    correction_count: int = 0
    error_type: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    execution_ms: Optional[int] = None
    row_count: Optional[int] = None
    chart_type: Optional[str] = None
    explanation: Optional[str] = None
    result_hash: Optional[str] = None
    
    # Reproducibility Provenance
    schema_snapshot_id: Optional[str] = None
    prompt_version: Optional[str] = None
    model_name: Optional[str] = None
    model_params: Optional[Dict[str, Any]] = None
    reliability_breakdown: Optional[Dict[str, Any]] = None
    
    critic_findings: List[Dict[str, Any]] = Field(default_factory=list)
    validations: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())


class QueryHistoryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[QueryHistorySummary]


class QueryRerunRequest(BaseModel):
    role_id: Optional[int] = None
    data_source_id: int = 1
    timeout_seconds: int = 10
    max_rows: int = 1000

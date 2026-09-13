from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class OptimizeExplainRequest(BaseModel):
    sql: str
    query_id: Optional[str] = None
    dialect: str = "sqlite"
    role_name: str = "analyst"


class OptimizeAnalyzeRequest(BaseModel):
    sql: str
    query_id: Optional[str] = None
    dialect: str = "sqlite"
    role_name: str = "admin"


class OptimizationEvidence(BaseModel):
    observed: str
    estimated_rows: Optional[float] = None
    actual_rows: Optional[float] = None
    filter_condition: Optional[str] = None
    existing_indexes: List[str] = Field(default_factory=list)
    cost: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class OptimizationItem(BaseModel):
    suggestion_id: Optional[int] = None
    issue_type: str
    detail: str
    evidence_json: Dict[str, Any]
    confidence: str = "medium"  # 'low' | 'medium' | 'high'
    suggested_ddl: Optional[str] = None


class OptimizeResponse(BaseModel):
    mode: str = "explain"  # 'explain' | 'explain_analyze'
    plan_raw: Any
    plan_summary: Dict[str, Any]
    suggestions: List[OptimizationItem]
    execution_stats: Optional[Dict[str, Any]] = None
    query_id: Optional[str] = None
    created_at: str

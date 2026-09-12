from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from app.schemas.policy import PolicyValidationResult


class CriticFindingType(str, Enum):
    AGGREGATE_ON_IDENTIFIER = "aggregate_on_identifier"
    SUSPICIOUS_GROUP_BY = "suspicious_group_by"
    REDUNDANT_JOIN = "redundant_join"
    COUNT_ON_LEFT_JOIN = "count_on_left_join"
    MISSING_LIMIT = "missing_limit"
    TYPE_MISMATCH_FILTER = "type_mismatch_filter"


class CriticFinding(BaseModel):
    finding_id: Optional[int] = None
    finding_type: CriticFindingType
    severity: str = "warning"  # "warning" | "advisory"
    title: str
    detail: str
    suggested_fix: Optional[str] = None
    suggested_sql: Optional[str] = None
    user_action: Optional[str] = None  # 'proceeded' | 'revised' | 'fix_applied'


class CriticAnalysisResult(BaseModel):
    has_findings: bool
    findings_count: int = 0
    findings: List[CriticFinding] = Field(default_factory=list)


class SQLProposal(BaseModel):
    sql: str
    rationale: str
    is_proposal: bool = True


class SQLGenerateRequest(BaseModel):
    question: str
    data_source_id: int = 1
    role_id: int = 4  # Default to viewer/analyst role
    session_id: Optional[str] = None
    clarifications: Optional[Dict[str, Any]] = None


class SQLGenerateResponse(BaseModel):
    question: str
    proposal: SQLProposal
    policy_validation: PolicyValidationResult
    critic_analysis: Optional[CriticAnalysisResult] = None
    can_execute: bool
    rejection_reasons: List[str] = Field(default_factory=list)


class SQLValidateRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 4


class SQLValidateResponse(BaseModel):
    sql: str
    policy_validation: PolicyValidationResult
    critic_analysis: Optional[CriticAnalysisResult] = None
    analysis: Optional[Dict[str, Any]] = None


class SQLCriticRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 1
    query_id: Optional[str] = None


class SQLCriticResponse(BaseModel):
    sql: str
    critic_analysis: CriticAnalysisResult


class SQLExecuteRequest(BaseModel):
    sql: str
    data_source_id: int = 1
    role_id: int = 4
    timeout_seconds: float = 10.0
    max_rows: int = 10000


class SQLExecuteResponse(BaseModel):
    success: bool
    sql: str
    injected_sql: Optional[str] = None
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    latency_ms: int = 0
    truncated: bool = False
    policy_validation: PolicyValidationResult
    critic_analysis: Optional[CriticAnalysisResult] = None
    error: Optional[str] = None
